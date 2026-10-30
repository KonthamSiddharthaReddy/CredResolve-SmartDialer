import React from 'react';
import { Call, CallState } from '../types';
import { PhoneCall } from 'lucide-react';

interface LiveCallsTableProps {
  calls: Call[];
}

export const LiveCallsTable: React.FC<LiveCallsTableProps> = ({ calls }) => {
  const getCallBadge = (status: CallState, isAbandoned: boolean) => {
    if (isAbandoned) {
      return (
        <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-red-500/20 text-red-400 border border-red-500/30">
          ABANDONED
        </span>
      );
    }
    switch (status) {
      case 'CONNECTED':
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 animate-pulse">
            CONNECTED
          </span>
        );
      case 'RINGING':
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-amber-500/20 text-amber-300 border border-amber-500/30">
            RINGING
          </span>
        );
      case 'INITIATED':
      case 'RESERVED':
      case 'QUEUED':
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-blue-500/20 text-blue-300 border border-blue-500/30">
            {status}
          </span>
        );
      case 'COMPLETED':
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-gray-700 text-gray-300">
            COMPLETED
          </span>
        );
      case 'FAILED':
      default:
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-red-900/40 text-red-300">
            FAILED
          </span>
        );
    }
  };

  return (
    <div className="bg-[#111827] border border-gray-800 rounded-xl p-5 flex flex-col gap-3">
      <div className="flex items-center justify-between border-b border-gray-800/80 pb-3">
        <div className="flex items-center gap-2">
          <PhoneCall className="w-4 h-4 text-emerald-400" />
          <h2 className="text-sm font-bold text-white tracking-wide">
            Active Outbound Calls ({calls.length})
          </h2>
        </div>
        <span className="text-xs text-gray-500 font-mono">
          Live Call Lifecycle
        </span>
      </div>

      <div className="overflow-x-auto max-h-60 overflow-y-auto">
        <table className="w-full text-left text-xs font-mono">
          <thead className="bg-[#0A0E17] text-gray-400 text-[11px] uppercase tracking-wider sticky top-0 border-b border-gray-800">
            <tr>
              <th className="py-2.5 px-3">Call ID</th>
              <th className="py-2.5 px-3">Status</th>
              <th className="py-2.5 px-3">Agent</th>
              <th className="py-2.5 px-3">Provider</th>
              <th className="py-2.5 px-3">Talk / Ring</th>
              <th className="py-2.5 px-3">Idempotency Key</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-800/50 text-gray-300">
            {calls.length === 0 ? (
              <tr>
                <td colSpan={6} className="py-6 text-center text-gray-500">
                  No active calls at this moment. Trigger a dialing cycle to initiate outbound calls.
                </td>
              </tr>
            ) : (
              calls.map(call => (
                <tr key={call.id} className="hover:bg-gray-800/30 transition-colors">
                  <td className="py-2 px-3 font-semibold text-white">#{call.id}</td>
                  <td className="py-2 px-3">{getCallBadge(call.status, call.is_abandoned)}</td>
                  <td className="py-2 px-3">
                    {call.agent_id ? (
                      <span className="text-blue-400 font-semibold">Agent #{call.agent_id}</span>
                    ) : (
                      <span className="text-gray-500 italic">Unassigned (Speculative)</span>
                    )}
                  </td>
                  <td className="py-2 px-3 text-gray-400">{call.provider_type}</td>
                  <td className="py-2 px-3 text-gray-300">
                    {call.talk_duration_seconds > 0
                      ? `${call.talk_duration_seconds.toFixed(0)}s talk`
                      : (call.ring_duration_seconds > 0 ? `${call.ring_duration_seconds.toFixed(0)}s ring` : '0s')}
                  </td>
                  <td className="py-2 px-3 text-[10px] text-gray-500 truncate max-w-[150px]" title={call.idempotency_key}>
                    {call.idempotency_key}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
