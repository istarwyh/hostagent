"use client";

import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { ToolApprovalInterrupt } from "@/app/components/ToolApprovalInterrupt";
import type {
  ToolApprovalDecision,
  ApprovalInterrupt,
  ToolApprovalCommandResume,
} from "@/app/types/types";
import {
  buildInterruptResume,
  getAllowedDecisions,
  getReviewConfig,
} from "@/app/utils/toolApproval";

interface ToolApprovalBatchProps {
  interrupts: ApprovalInterrupt[];
  onResume: (value: ToolApprovalCommandResume) => void;
  isLoading?: boolean;
  error?: unknown;
}

// The parent keys this component by interrupt and thread to reset saved decisions.
export function ToolApprovalBatch({
  interrupts,
  onResume,
  isLoading,
  error,
}: ToolApprovalBatchProps) {
  const actions = interrupts.flatMap(({ value }) =>
    value.action_requests.map((request, index) => ({
      request,
      reviewConfig: getReviewConfig(value.review_configs, request, index),
    }))
  );
  const [decisions, setDecisions] = useState<(ToolApprovalDecision | undefined)[]>(
    () => Array.from({ length: actions.length })
  );
  const decisionsRef = useRef(decisions);
  const submittedRef = useRef(false);

  useEffect(() => {
    if (!isLoading) submittedRef.current = false;
  }, [isLoading]);

  const submitDecisions = (resume: ToolApprovalCommandResume) => {
    if (isLoading || submittedRef.current) return;
    submittedRef.current = true;
    onResume(resume);
  };

  const recordDecision = (index: number, decision: ToolApprovalDecision) => {
    if (isLoading || submittedRef.current || decisionsRef.current[index]) return;
    const config = actions[index].reviewConfig;
    if (!getAllowedDecisions(config).includes(decision.type)) return;
    const nextDecisions = [...decisionsRef.current];
    nextDecisions[index] = decision;
    decisionsRef.current = nextDecisions;
    setDecisions(nextDecisions);
    const resume = buildInterruptResume(interrupts, nextDecisions);
    if (resume) submitDecisions(resume);
  };

  const completedResume = buildInterruptResume(interrupts, decisions);

  return (
    <div className="mt-4 space-y-3">
      <p
        className="text-sm text-muted-foreground"
        role="status"
      >
        {decisions.filter(Boolean).length} of {actions.length} decisions saved. The agent will resume after every action has a decision.
      </p>
      {!isLoading && completedResume && (
        <div
          role="alert"
          className="text-sm text-destructive"
        >
          <p>
            {error ? "Unable to resume." : "The agent is still paused."}{" "}
            Your decisions are saved.
          </p>
          <Button
            variant="outline"
            size="sm"
            onClick={() => submitDecisions(completedResume)}
          >
            Retry resume
          </Button>
        </div>
      )}
      {actions.map(({ request, reviewConfig }, index) => (
        <ToolApprovalInterrupt
          key={index}
          actionRequest={request}
          reviewConfig={reviewConfig}
          decision={decisions[index]}
          onDecision={(decision) => recordDecision(index, decision)}
          isLoading={isLoading}
        />
      ))}
    </div>
  );
}
