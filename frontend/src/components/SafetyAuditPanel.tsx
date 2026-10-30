import React from 'react';
import { SafetyDecisionAudit, SafetyDecisionType } from '../types';
import { ShieldCheck, AlertCircle, ArrowRight, CornerDownRight, CheckCircle2, XCircle } from 'lucide-react';

interface SafetyAuditPanelProps {
  lastDecision: SafetyDecisionAudit | null;
  history: SafetyDecisionAudit[];
}

export const SafetyAuditPanel: React.FC<SafetyAuditPanelProps> = ({ lastDecision, history }) => {
  const getDecisionBadge = (type: SafetyDecisionType) => {
    switch (type) {
      case 'APPROVED':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <CheckCircle2 className="w-3.5 h-3.5" /> APPROVED
          </span>
        );
      case 'REDUCED':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/20">
            <AlertCircle className="w-3.5 h-3.5" /> REDUCED (CLAMPED)
          </span>
        );
      case 'FALLBACK_PROGRESSIVE':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-purple-500/10 text-purple-400 border border-purple-500/20">
            <CornerDownRight className="w-3.5 h-3.5" /> FALLBACK TO PROGRESSIVE
          </span>
        );
      case 'REJECTED':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-red-500/10 text-red-400 border border-red-500/20">
            <XCircle className="w-3.5 h-3.5" /> REJECTED
          </span>
        );
      default:
        return null;
    }
  };

  return (
    <div className="bg-[#111827] border border-gray-800 rounded-xl p-5 flex flex-col gap-5">
      {/* Panel Header */}
      <div className="flex items-center justify-between border-b border-gray-800/80 pb-3">
        <div className="flex items-center gap-2.5">
          <div className="p-2 bg-blue-500/10 rounded-lg text-blue-400 border border-blue-500/20">
            <ShieldCheck className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-sm font-bold text-white tracking-wide">
              Independent Safety Controller & Pacing Audit
            </h2>
            <p className="text-xs text-gray-400">
              Autonomous gatekeeper enforcing compliance buffers & deterministic safety
            </p>
          </div>
        </div>

        {lastDecision && getDecisionBadge(lastDecision.decision_type)}
      </div>

      {/* Latest Decision Deep Dive */}
      {lastDecision ? (
        <div className="bg-[#0A0E17] border border-gray-800 rounded-lg p-4 space-y-3">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 text-xs">
            <div className="flex items-center gap-3">
              <div className="text-gray-400">Engine Request:</div>
              <span className="text-sm font-bold text-purple-400 font-mono">
                {lastDecision.requested_calls} calls ({lastDecision.dialing_mode})
              </span>
              <ArrowRight className="w-3.5 h-3.5 text-gray-500" />
              <div className="text-gray-400">Safety Approved:</div>
              <span className="text-sm font-bold text-emerald-400 font-mono">
                {lastDecision.approved_calls} calls
              </span>
            </div>

            <div className="text-gray-500 font-mono text-[11px]">
              {new Date(lastDecision.timestamp).toLocaleTimeString()}
            </div>
          </div>

          <div className="text-xs text-gray-200 bg-[#111827] p-3 rounded border border-gray-800 leading-relaxed font-mono">
            <span className="text-blue-400 font-bold">Decision Rationale: </span>
            {lastDecision.rationale}
          </div>

          {/* Mathematical Factors Grid */}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-2 pt-1 text-[11px] font-mono">
            <div className="bg-gray-900/60 p-2 rounded border border-gray-800/50">
              <span className="text-gray-500 block">Available Agents:</span>
              <span className="font-semibold text-white">{lastDecision.available_agents}</span>
            </div>
            <div className="bg-gray-900/60 p-2 rounded border border-gray-800/50">
              <span className="text-gray-500 block">In-Flight Ringing:</span>
              <span className="font-semibold text-amber-400">{lastDecision.ringing_calls}</span>
            </div>
            <div className="bg-gray-900/60 p-2 rounded border border-gray-800/50">
              <span className="text-gray-500 block">Connected Calls:</span>
              <span className="font-semibold text-emerald-400">{lastDecision.connected_calls}</span>
            </div>
            <div className="bg-gray-900/60 p-2 rounded border border-gray-800/50">
              <span className="text-gray-500 block">Exp. Freeing Release:</span>
              <span className="font-semibold text-indigo-400">{lastDecision.expected_free_agents.toFixed(1)}</span>
            </div>
            <div className="bg-gray-900/60 p-2 rounded border border-gray-800/50">
              <span className="text-gray-500 block">Carrier Status:</span>
              <span className="font-semibold text-green-400">{lastDecision.provider_health_status}</span>
            </div>
          </div>
        </div>
      ) : (
        <div className="text-center py-6 text-xs text-gray-500 font-mono">
          No dialing decisions recorded yet. Start simulation or run cycle to observe safety logic.
        </div>
      )}

      {/* Decision History Feed */}
      {history.length > 1 && (
        <div className="space-y-1.5">
          <span className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider block">
            Recent Audit Trail
          </span>
          <div className="max-h-36 overflow-y-auto space-y-1.5 pr-1 font-mono text-[11px]">
            {history.slice(1, 8).map((audit) => (
              <div
                key={audit.id}
                className="flex items-center justify-between p-2 rounded bg-[#0A0E17]/60 border border-gray-800/40 text-gray-400"
              >
                <div className="flex items-center gap-2 truncate">
                  <span className="text-[10px] text-gray-500">
                    {new Date(audit.timestamp).toLocaleTimeString()}
                  </span>
                  <span className="text-gray-300">
                    Req: {audit.requested_calls} → Appr: {audit.approved_calls}
                  </span>
                  <span className="text-gray-500 truncate max-w-md">
                    ({audit.rationale})
                  </span>
                </div>
                <div className="flex-shrink-0">
                  {getDecisionBadge(audit.decision_type)}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
