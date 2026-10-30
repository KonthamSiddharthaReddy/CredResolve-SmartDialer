import React from 'react';
import { SystemMetrics } from '../types';
import { Users, PhoneCall, Activity, ShieldCheck, AlertTriangle, Radio } from 'lucide-react';

interface MetricsBarProps {
  metrics: SystemMetrics | null;
}

export const MetricsBar: React.FC<MetricsBarProps> = ({ metrics }) => {
  if (!metrics) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-6 gap-4 animate-pulse">
        {[...Array(6)].map((_, i) => (
          <div key={i} className="h-24 bg-gray-900 rounded-lg border border-gray-800" />
        ))}
      </div>
    );
  }

  const isAbandonSafe = metrics.abandoned_calls === 0;

  return (
    <div className="grid grid-cols-2 lg:grid-cols-6 gap-4">
      {/* 1. Agent Capacity */}
      <div className="bg-[#111827] border border-gray-800 rounded-xl p-4 flex flex-col justify-between">
        <div className="flex items-center justify-between text-gray-400 text-xs font-medium uppercase tracking-wider">
          <span>Available Agents</span>
          <Users className="w-4 h-4 text-emerald-400" />
        </div>
        <div className="mt-2 flex items-baseline gap-2">
          <span className="text-3xl font-bold text-white tracking-tight">{metrics.available_agents}</span>
          <span className="text-xs text-gray-400 font-mono">/ {metrics.total_agents} total</span>
        </div>
        <div className="mt-2 flex items-center gap-1.5 text-xs text-gray-400 font-mono">
          <span className="w-2 h-2 rounded-full bg-emerald-500 inline-block"></span>
          <span>{metrics.connected_agents} on calls</span>
          <span className="text-gray-600">|</span>
          <span>{metrics.wrap_up_agents} wrap</span>
        </div>
      </div>

      {/* 2. Agent Utilization */}
      <div className="bg-[#111827] border border-gray-800 rounded-xl p-4 flex flex-col justify-between">
        <div className="flex items-center justify-between text-gray-400 text-xs font-medium uppercase tracking-wider">
          <span>Agent Utilization</span>
          <Activity className="w-4 h-4 text-blue-400" />
        </div>
        <div className="mt-2 flex items-baseline gap-2">
          <span className="text-3xl font-bold text-blue-400 tracking-tight">
            {metrics.agent_utilization_rate}%
          </span>
        </div>
        <div className="mt-2 w-full bg-gray-800 h-1.5 rounded-full overflow-hidden">
          <div
            className="bg-blue-500 h-full rounded-full transition-all duration-500"
            style={{ width: `${Math.min(100, metrics.agent_utilization_rate)}%` }}
          />
        </div>
      </div>

      {/* 3. Calls In Flight */}
      <div className="bg-[#111827] border border-gray-800 rounded-xl p-4 flex flex-col justify-between">
        <div className="flex items-center justify-between text-gray-400 text-xs font-medium uppercase tracking-wider">
          <span>Ringing Calls</span>
          <PhoneCall className="w-4 h-4 text-amber-400" />
        </div>
        <div className="mt-2 flex items-baseline gap-2">
          <span className="text-3xl font-bold text-amber-400 tracking-tight">
            {metrics.ringing_calls}
          </span>
          <span className="text-xs text-gray-400 font-mono">in-flight</span>
        </div>
        <div className="mt-2 text-xs text-gray-400 font-mono">
          <span>{metrics.queued_borrowers} in queue</span>
        </div>
      </div>

      {/* 4. Active Connected Calls */}
      <div className="bg-[#111827] border border-gray-800 rounded-xl p-4 flex flex-col justify-between">
        <div className="flex items-center justify-between text-gray-400 text-xs font-medium uppercase tracking-wider">
          <span>Connected Calls</span>
          <Activity className="w-4 h-4 text-green-400" />
        </div>
        <div className="mt-2 flex items-baseline gap-2">
          <span className="text-3xl font-bold text-green-400 tracking-tight">
            {metrics.connected_calls}
          </span>
          <span className="text-xs text-gray-400 font-mono">live conversation</span>
        </div>
        <div className="mt-2 text-xs text-gray-400 font-mono">
          <span>{metrics.completed_calls} completed</span>
        </div>
      </div>

      {/* 5. Abandoned Calls (Crucial Compliance Guard) */}
      <div className={`border rounded-xl p-4 flex flex-col justify-between ${
        isAbandonSafe ? 'bg-[#111827] border-gray-800' : 'bg-red-950/30 border-red-800'
      }`}>
        <div className="flex items-center justify-between text-xs font-medium uppercase tracking-wider">
          <span className={isAbandonSafe ? 'text-gray-400' : 'text-red-400 font-bold'}>
            Abandoned Calls
          </span>
          {isAbandonSafe ? (
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
          ) : (
            <AlertTriangle className="w-4 h-4 text-red-400 animate-bounce" />
          )}
        </div>
        <div className="mt-2 flex items-baseline gap-2">
          <span className={`text-3xl font-bold tracking-tight ${isAbandonSafe ? 'text-white' : 'text-red-400'}`}>
            {metrics.abandoned_calls}
          </span>
          <span className="text-xs font-mono text-gray-400">
            ({metrics.abandon_rate}%)
          </span>
        </div>
        <div className="mt-2 text-[11px] font-mono">
          <span className={isAbandonSafe ? 'text-emerald-400' : 'text-red-400 font-semibold'}>
            {isAbandonSafe ? 'Compliant (Zero Abandoned)' : 'REGULATORY RISK TRIGGERED'}
          </span>
        </div>
      </div>

      {/* 6. Answer Rate & Carrier Status */}
      <div className="bg-[#111827] border border-gray-800 rounded-xl p-4 flex flex-col justify-between">
        <div className="flex items-center justify-between text-gray-400 text-xs font-medium uppercase tracking-wider">
          <span>Answer Rate & Carrier</span>
          <Radio className="w-4 h-4 text-indigo-400" />
        </div>
        <div className="mt-2 flex items-baseline gap-2">
          <span className="text-3xl font-bold text-indigo-400 tracking-tight">
            {(metrics.estimated_answer_rate * 100).toFixed(0)}%
          </span>
          <span className="text-xs text-gray-400 font-mono">est.</span>
        </div>
        <div className="mt-2 flex items-center justify-between text-[11px] font-mono">
          <span className="flex items-center gap-1">
            <span className={`w-2 h-2 rounded-full ${metrics.provider_a_circuit === 'CLOSED' ? 'bg-emerald-400' : 'bg-red-500'}`} />
            PA: {metrics.provider_a_circuit}
          </span>
          <span className="flex items-center gap-1">
            <span className={`w-2 h-2 rounded-full ${metrics.provider_b_circuit === 'CLOSED' ? 'bg-emerald-400' : 'bg-red-500'}`} />
            PB: {metrics.provider_b_circuit}
          </span>
        </div>
      </div>
    </div>
  );
};
