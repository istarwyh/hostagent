import type {
  ActionRequest,
  ApprovalInterrupt,
  ReviewConfig,
  ToolApprovalDecision,
  ToolApprovalCommandResume,
  ToolApprovalResume,
} from "../types/types";

export function getAllowedDecisions(
  reviewConfig?: ReviewConfig
): ToolApprovalDecision["type"][] {
  return (
    reviewConfig?.allowed_decisions ??
    reviewConfig?.allowedDecisions ?? ["approve", "reject", "edit"]
  );
}

export function getReviewConfig(
  reviewConfigs: ReviewConfig[] | undefined,
  actionRequest: ActionRequest,
  index: number
) {
  const matches = (config: ReviewConfig) =>
    (config.action_name ?? config.actionName) === actionRequest.name;
  const indexedConfig = reviewConfigs?.[index];
  return indexedConfig && matches(indexedConfig)
    ? indexedConfig
    : reviewConfigs?.find(matches);
}

export function buildApprovalResume(
  decisions: (ToolApprovalDecision | undefined)[]
): ToolApprovalResume | undefined {
  const complete = decisions.filter(
    (decision): decision is ToolApprovalDecision => !!decision
  );
  if (!complete.length || complete.length !== decisions.length) return undefined;
  return { decisions: complete };
}

interface InterruptState {
  tasks?: { interrupts?: unknown[]; state?: InterruptState | null }[];
}

export function collectApprovalInterrupts(
  streamedInterrupts: unknown,
  state?: InterruptState
) {
  const found: unknown[] = [];
  const collectTasks = (current?: InterruptState) => {
    for (const task of current?.tasks ?? []) {
      found.push(...(task.interrupts ?? []));
      if (task.state) collectTasks(task.state);
    }
  };
  if (Array.isArray(streamedInterrupts)) found.push(...streamedInterrupts);
  else collectTasks(state);
  const interrupts = new Map<string, ApprovalInterrupt>();
  for (const value of found) {
    if (!value || typeof value !== "object") continue;
    const interrupt = value as ApprovalInterrupt;
    if (
      !Array.isArray(interrupt.value?.action_requests) ||
      !interrupt.value.action_requests.length
    ) continue;
    interrupts.set(interrupt.id ?? JSON.stringify(value), interrupt);
  }
  return Array.from(interrupts.values());
}

export function buildInterruptResume(
  interrupts: ApprovalInterrupt[],
  decisions: (ToolApprovalDecision | undefined)[]
): ToolApprovalCommandResume | undefined {
  const complete = buildApprovalResume(decisions);
  const total = interrupts.reduce(
    (count, interrupt) => count + interrupt.value.action_requests.length,
    0
  );
  if (!complete || complete.decisions.length !== total) return undefined;
  if (interrupts.length === 1 && !interrupts[0].id) return complete;
  if (interrupts.some((interrupt) => !interrupt.id)) return undefined;
  let offset = 0;
  return Object.fromEntries(
    interrupts.map((interrupt) => {
      const count = interrupt.value.action_requests.length;
      const batch = { decisions: complete.decisions.slice(offset, offset + count) };
      offset += count;
      return [interrupt.id!, batch];
    })
  );
}
