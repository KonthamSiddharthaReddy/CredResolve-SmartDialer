import React, { useState } from 'react';
import { AlertOctagon, RefreshCw, ZapOff, TrendingDown, Skull, Copy, Shuffle, HeartPulse } from 'lucide-react';

interface FailureInjectionPanelProps {
  onInject: (type: string, params?: Record<string, any>) => Promise<any>;
  onTriggerRecovery: () => Promise<any>;
}

export const FailureInjectionPanel: React.FC<FailureInjectionPanelProps> = ({
  onInject,
  onTriggerRecovery
}) => {
  const [feedback, setFeedback] = useState<string | null>(null);
  const [loadingAction, setLoadingAction] = useState<string | null>(null);

  const handleAction = async (actionName: string, fn: () => Promise<any>) => {
    try {
      setLoadingAction(actionName);
      setFeedback(null);
      const res = await fn();
      setFeedback(`Executed: ${actionName} -> ${JSON.stringify(res.message || res.action || res.status)}`);
    } catch (e: any) {
      setFeedback(`Error: ${e.message}`);
    } finally {
      setLoadingAction(null);
    }
  };

  return (
    <div className="bg-[#111827] border border-gray-800 rounded-xl p-5 flex flex-col gap-4">
      <div className="flex items-center justify-between border-b border-gray-800/80 pb-3">
        <div className="flex items-center gap-2">
          <AlertOctagon className="w-4 h-4 text-rose-400" />
          <h2 className="text-sm font-bold text-white tracking-wide">
            Chaos & Failure Simulation Suite
          </h2>
        </div>
        <span className="text-xs text-rose-400 font-mono">
          Assignment Test Scenarios 1–7
        </span>
      </div>

      {feedback && (
        <div className="p-2.5 rounded bg-blue-950/40 border border-blue-800 text-blue-300 text-xs font-mono">
          {feedback}
        </div>
      )}

      {/* Action Buttons Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-2.5 text-xs font-mono">
        {/* 1. Drop 40 Agents */}
        <button
          onClick={() => handleAction('Drop 40 Agents', () => onInject('DROP_AGENTS', { count: 40 }))}
          disabled={loadingAction !== null}
          className="p-2.5 rounded-lg bg-red-950/30 hover:bg-red-900/50 border border-red-800/60 text-red-300 flex flex-col items-start gap-1 transition-all"
        >
          <div className="flex items-center gap-1.5 font-bold">
            <ZapOff className="w-3.5 h-3.5 text-red-400" /> Drop 40 Agents
          </div>
          <span className="text-[10px] text-gray-400">100 → 60 sudden drop</span>
        </button>

        {/* 2. Restore Agents */}
        <button
          onClick={() => handleAction('Restore Agents', () => onInject('RESTORE_AGENTS'))}
          disabled={loadingAction !== null}
          className="p-2.5 rounded-lg bg-emerald-950/30 hover:bg-emerald-900/50 border border-emerald-800/60 text-emerald-300 flex flex-col items-start gap-1 transition-all"
        >
          <div className="flex items-center gap-1.5 font-bold">
            <RefreshCw className="w-3.5 h-3.5 text-emerald-400" /> Restore Agents
          </div>
          <span className="text-[10px] text-gray-400">Move offline → available</span>
        </button>

        {/* 3. Provider Outage */}
        <button
          onClick={() => handleAction('Provider Outage', () => onInject('PROVIDER_OUTAGE'))}
          disabled={loadingAction !== null}
          className="p-2.5 rounded-lg bg-amber-950/30 hover:bg-amber-900/50 border border-amber-800/60 text-amber-300 flex flex-col items-start gap-1 transition-all"
        >
          <div className="flex items-center gap-1.5 font-bold">
            <AlertOctagon className="w-3.5 h-3.5 text-amber-400" /> Carrier Outage
          </div>
          <span className="text-[10px] text-gray-400">Trip Circuit Breaker</span>
        </button>

        {/* 4. Restore Provider */}
        <button
          onClick={() => handleAction('Restore Carrier', () => onInject('RESTORE_PROVIDER'))}
          disabled={loadingAction !== null}
          className="p-2.5 rounded-lg bg-blue-950/30 hover:bg-blue-900/50 border border-blue-800/60 text-blue-300 flex flex-col items-start gap-1 transition-all"
        >
          <div className="flex items-center gap-1.5 font-bold">
            <RefreshCw className="w-3.5 h-3.5 text-blue-400" /> Restore Carrier
          </div>
          <span className="text-[10px] text-gray-400">Reset circuit to CLOSED</span>
        </button>

        {/* 5. Crash Answer Rate */}
        <button
          onClick={() => handleAction('Answer Rate Crash', () => onInject('ANSWER_RATE_CRASH', { rate: 0.10 }))}
          disabled={loadingAction !== null}
          className="p-2.5 rounded-lg bg-purple-950/30 hover:bg-purple-900/50 border border-purple-800/60 text-purple-300 flex flex-col items-start gap-1 transition-all"
        >
          <div className="flex items-center gap-1.5 font-bold">
            <TrendingDown className="w-3.5 h-3.5 text-purple-400" /> Crash Ans Rate
          </div>
          <span className="text-[10px] text-gray-400">Crash 70% → 10%</span>
        </button>

        {/* 6. Worker Crash */}
        <button
          onClick={() => handleAction('Worker Crash', () => onInject('WORKER_CRASH'))}
          disabled={loadingAction !== null}
          className="p-2.5 rounded-lg bg-rose-950/30 hover:bg-rose-900/50 border border-rose-800/60 text-rose-300 flex flex-col items-start gap-1 transition-all"
        >
          <div className="flex items-center gap-1.5 font-bold">
            <Skull className="w-3.5 h-3.5 text-rose-400" /> Worker Crash
          </div>
          <span className="text-[10px] text-gray-400">Leave stale reservations</span>
        </button>

        {/* 7. Duplicate Webhook */}
        <button
          onClick={() => handleAction('Duplicate Webhook', () => onInject('INJECT_DUPLICATE_WEBHOOK'))}
          disabled={loadingAction !== null}
          className="p-2.5 rounded-lg bg-gray-900 hover:bg-gray-800 border border-gray-700 text-gray-200 flex flex-col items-start gap-1 transition-all"
        >
          <div className="flex items-center gap-1.5 font-bold">
            <Copy className="w-3.5 h-3.5 text-cyan-400" /> Duplicate Event
          </div>
          <span className="text-[10px] text-gray-400">Send duplicate ANSWERED</span>
        </button>

        {/* 8. Out-of-order Webhook */}
        <button
          onClick={() => handleAction('Out-of-Order Webhook', () => onInject('INJECT_OUT_OF_ORDER'))}
          disabled={loadingAction !== null}
          className="p-2.5 rounded-lg bg-gray-900 hover:bg-gray-800 border border-gray-700 text-gray-200 flex flex-col items-start gap-1 transition-all"
        >
          <div className="flex items-center gap-1.5 font-bold">
            <Shuffle className="w-3.5 h-3.5 text-amber-400" /> Out-of-Order Event
          </div>
          <span className="text-[10px] text-gray-400">COMPLETED before ANSWERED</span>
        </button>

        {/* 9. Janitor / Reaper Recovery */}
        <button
          onClick={() => handleAction('Run Janitor Reaper', () => onTriggerRecovery())}
          disabled={loadingAction !== null}
          className="p-2.5 rounded-lg bg-green-950/30 hover:bg-green-900/50 border border-green-800/60 text-green-300 flex flex-col items-start gap-1 transition-all col-span-2 md:col-span-1"
        >
          <div className="flex items-center gap-1.5 font-bold">
            <HeartPulse className="w-3.5 h-3.5 text-green-400" /> Janitor Reaper
          </div>
          <span className="text-[10px] text-gray-400">Reap stale locks & calls</span>
        </button>
      </div>
    </div>
  );
};
