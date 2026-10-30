import React, { useState } from 'react';
import { Agent, AgentState } from '../types';
import { Users } from 'lucide-react';

interface AgentGridProps {
  agents: Agent[];
}

export const AgentGrid: React.FC<AgentGridProps> = ({ agents }) => {
  const [filter, setFilter] = useState<string>('ALL');

  const filteredAgents = filter === 'ALL'
    ? agents
    : agents.filter(a => a.status === filter);

  const getStatusColor = (status: AgentState) => {
    switch (status) {
      case 'AVAILABLE':
        return 'bg-emerald-500/15 border-emerald-500/40 text-emerald-300';
      case 'RESERVED':
        return 'bg-cyan-500/20 border-cyan-500/40 text-cyan-300';
      case 'DIALING':
        return 'bg-blue-500/20 border-blue-500/40 text-blue-300';
      case 'CONNECTED':
        return 'bg-green-500/25 border-green-500/60 text-green-200 shadow-sm shadow-green-500/20 animate-pulse';
      case 'WRAP_UP':
        return 'bg-amber-500/20 border-amber-500/40 text-amber-300';
      case 'PAUSED':
        return 'bg-purple-500/15 border-purple-500/30 text-purple-300';
      case 'OFFLINE':
      default:
        return 'bg-gray-800/40 border-gray-700/30 text-gray-500';
    }
  };

  const counts: Record<string, number> = {
    ALL: agents.length,
    AVAILABLE: agents.filter(a => a.status === 'AVAILABLE').length,
    CONNECTED: agents.filter(a => a.status === 'CONNECTED').length,
    WRAP_UP: agents.filter(a => a.status === 'WRAP_UP').length,
    OFFLINE: agents.filter(a => a.status === 'OFFLINE').length,
  };

  return (
    <div className="bg-[#111827] border border-gray-800 rounded-xl p-5 flex flex-col gap-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-gray-800/80 pb-3">
        <div className="flex items-center gap-2">
          <Users className="w-4 h-4 text-blue-400" />
          <h2 className="text-sm font-bold text-white tracking-wide">
            Live Agent Allocation Matrix ({agents.length} Total)
          </h2>
        </div>

        {/* State Filters */}
        <div className="flex flex-wrap items-center gap-1.5 text-xs font-mono">
          {(['ALL', 'AVAILABLE', 'CONNECTED', 'WRAP_UP', 'OFFLINE'] as const).map(tab => (
            <button
              key={tab}
              onClick={() => setFilter(tab)}
              className={`px-2.5 py-1 rounded transition-all ${
                filter === tab
                  ? 'bg-blue-600 text-white font-semibold shadow-sm'
                  : 'bg-gray-900 text-gray-400 hover:text-white hover:bg-gray-800'
              }`}
            >
              {tab} ({counts[tab] || 0})
            </button>
          ))}
        </div>
      </div>

      {/* Grid of Agents */}
      <div className="grid grid-cols-4 sm:grid-cols-6 md:grid-cols-10 gap-2 max-h-56 overflow-y-auto pr-1">
        {filteredAgents.map(agent => (
          <div
            key={agent.id}
            title={`Agent #${agent.id} - ${agent.status}\nCalls Handled: ${agent.total_calls_handled}\nTalk Time: ${agent.total_talk_time_seconds.toFixed(0)}s\nOptimistic Version: v${agent.version}`}
            className={`border rounded-lg p-2 flex flex-col items-center justify-center cursor-pointer transition-transform hover:scale-105 ${getStatusColor(
              agent.status
            )}`}
          >
            <span className="text-[11px] font-bold font-mono truncate w-full text-center">
              #{agent.id}
            </span>
            <span className="text-[9px] font-mono tracking-tight uppercase truncate max-w-full">
              {agent.status}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
};
