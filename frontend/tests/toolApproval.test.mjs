import assert from "node:assert/strict";
import test from "node:test";
import {
  buildApprovalResume,
  buildInterruptResume,
  collectApprovalInterrupts,
  getAllowedDecisions,
  getReviewConfig,
} from "../src/app/utils/toolApproval.ts";

test("all decisions are required and retain request order, not click order", () => {
  const decisions = Array.from({ length: 3 });
  assert.equal(buildApprovalResume(decisions), undefined);
  decisions[2] = { type: "reject", message: "Skip this action" };
  assert.equal(buildApprovalResume(decisions), undefined);
  decisions[0] = { type: "approve" };
  assert.equal(buildApprovalResume(decisions), undefined);
  decisions[1] = {
    type: "edit",
    edited_action: { name: "write_file", args: { path: "/edited.txt" } },
  };
  assert.deepEqual(buildApprovalResume(decisions), { decisions });
  assert.deepEqual(
    buildApprovalResume(decisions).decisions.map(({ type }) => type),
    ["approve", "edit", "reject"]
  );
});

test("empty and sparse batches cannot resume", () => {
  assert.equal(buildApprovalResume([]), undefined);
  assert.equal(buildApprovalResume(new Array(2)), undefined);
});

test("v1 snake_case configs take precedence over legacy fields", () => {
  const config = {
    action_name: "write_file",
    actionName: "legacy_tool",
    allowed_decisions: ["approve", "reject"],
    allowedDecisions: ["edit"],
  };
  assert.equal(
    getReviewConfig([config], { name: "write_file", args: {} }, 0),
    config
  );
  assert.deepEqual(getAllowedDecisions(config), ["approve", "reject"]);
  assert.equal(
    getReviewConfig([config], { name: "legacy_tool", args: {} }, 0),
    undefined
  );
});

test("same-name actions keep their own indexed review configs", () => {
  const configs = [
    { action_name: "write_file", allowed_decisions: ["approve"] },
    { action_name: "write_file", allowed_decisions: ["reject"] },
  ];
  const action = { name: "write_file", args: {} };
  assert.equal(getReviewConfig(configs, action, 0), configs[0]);
  assert.equal(getReviewConfig(configs, action, 1), configs[1]);
});

test("legacy configs remain compatible and explicit empty decisions remain empty", () => {
  const config = { actionName: "task", allowedDecisions: ["approve"] };
  assert.equal(
    getReviewConfig([config], { name: "task", args: {} }, 4),
    config
  );
  assert.deepEqual(getAllowedDecisions(config), ["approve"]);
  assert.deepEqual(getAllowedDecisions({ allowed_decisions: [] }), []);
});

test("parallel and nested task interrupts keep their IDs and deduplicate snapshots", () => {
  const first = {
    id: "interrupt-a",
    value: {
      action_requests: [{ name: "write_file", args: { path: "/a" } }],
    },
  };
  const second = {
    id: "interrupt-b",
    value: {
      action_requests: [{ name: "write_file", args: { path: "/b" } }],
    },
  };
  const tasks = {
    tasks: [
      {
        interrupts: [first],
        state: { tasks: [{ interrupts: [first] }] },
      },
      { interrupts: [second] },
    ],
  };
  assert.deepEqual(collectApprovalInterrupts(undefined, tasks), [first, second]);
  assert.deepEqual(collectApprovalInterrupts([first, second], tasks), [
    first,
    second,
  ]);
  const approve = { type: "approve" };
  const reject = { type: "reject", message: "Skip second" };
  assert.equal(
    buildInterruptResume([first, second], [approve, undefined]),
    undefined
  );
  assert.deepEqual(buildInterruptResume([first, second], [approve, reject]), {
    "interrupt-a": { decisions: [approve] },
    "interrupt-b": { decisions: [reject] },
  });
});

test("explicit stream interrupts replace history and empty streams do not resurrect stale approvals", () => {
  const oldInterrupt = {
    id: "old",
    value: { action_requests: [{ name: "task", args: {} }] },
  };
  const nextInterrupt = {
    id: "next",
    value: { action_requests: [{ name: "task", args: {} }] },
  };
  const state = { tasks: [{ interrupts: [oldInterrupt] }] };
  assert.deepEqual(collectApprovalInterrupts([nextInterrupt], state), [
    nextInterrupt,
  ]);
  assert.deepEqual(collectApprovalInterrupts([], state), []);
  assert.deepEqual(collectApprovalInterrupts(undefined, { tasks: [] }), []);
});

test("multi-action interrupts are grouped under the correct interrupt ID", () => {
  const action = { name: "record", args: {} };
  const interrupts = [
    { id: "first", value: { action_requests: [action, action] } },
    { id: "second", value: { action_requests: [action] } },
  ];
  const decisions = [
    { type: "approve" },
    { type: "reject", message: "No" },
    { type: "edit", edited_action: action },
  ];
  assert.equal(
    buildInterruptResume(interrupts, decisions.slice(0, 2)),
    undefined
  );
  assert.deepEqual(buildInterruptResume(interrupts, decisions), {
    first: { decisions: decisions.slice(0, 2) },
    second: { decisions: decisions.slice(2) },
  });
  assert.deepEqual(
    buildInterruptResume(
      [{ value: { action_requests: [action] } }],
      [decisions[0]]
    ),
    { decisions: [decisions[0]] }
  );
  assert.equal(
    buildInterruptResume(
      [
        { value: { action_requests: [action] } },
        { value: { action_requests: [action] } },
      ],
      decisions.slice(0, 2)
    ),
    undefined
  );
});
