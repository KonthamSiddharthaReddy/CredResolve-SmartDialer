import React from 'react';
import { DialingMode, ProviderType } from '../types';
import { Shield, Zap, Server, Play } from 'lucide-react';

interface DialingControlPanelProps {
  currentMode: DialingMode;
  currentProvider: ProviderType;
  onUpdateMode: (mode: DialingMode) => void;
  onUpdateProvider: (provider: ProviderType) => void;
  onTriggerCycle: () => void;
  isTriggering: boolean;
}

export const DialingControlPanel: React.FC<DialingControlPanelProps> = ({
  currentMode,
  currentProvider,
  onUpdateMode,
  onUpdateProvider,
  onTriggerCycle,
  isTriggering
}) => {
  return (
    <div className="bg-[#111827] border border-gray-800 rounded-xl p-5">
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        
        {/* Mode Selector */}
        <div className="space-y-1.5">
          <label className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
            Dialing Engine Strategy
          </label>
          <div className="flex items-center gap-2 bg-[#0A0E17] p-1.5 rounded-lg border border-gray-800">
            <button
              onClick={() => onUpdateMode('PROGRESSIVE')}
              className={`flex items-center gap-2 px-3.5 py-1.5 rounded-md text-xs font-semibold transition-all ${
                currentMode === 'PROGRESSIVE'
                  ? 'bg-blue-600 text-white shadow-md'
                  : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800/50'
              }`}
            >
              <Shield className="w-3.5 h-3.5" />
              Progressive (1:1 Deterministic)
            </button>
            <button
              onClick={() => onUpdateMode('PREDICTIVE')}
              className={`flex items-center gap-2 px-3.5 py-1.5 rounded-md text-xs font-semibold transition-all ${
                currentMode === 'PREDICTIVE'
                  ? 'bg-purple-600 text-white shadow-md'
                  : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800/50'
              }`}
            >
              <Zap className="w-3.5 h-3.5" />
              Predictive (Statistical Pacing)
            </button>
          </div>
        </div>

        {/* Provider Selector */}
        <div className="space-y-1.5">
          <label className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
            Active Mock Telecom Provider
          </label>
          <div className="flex items-center gap-2 bg-[#0A0E17] p-1.5 rounded-lg border border-gray-800">
            <button
              onClick={() => onUpdateProvider('PROVIDER_A')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
                currentProvider === 'PROVIDER_A'
                  ? 'bg-emerald-600 text-white shadow-sm'
                  : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800/50'
              }`}
            >
              <Server className="w-3 h-3 text-emerald-200" />
              Provider A (Fast / Reliable)
            </button>
            <button
              onClick={() => onUpdateProvider('PROVIDER_B')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
                currentProvider === 'PROVIDER_B'
                  ? 'bg-amber-600 text-white shadow-sm'
                  : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800/50'
              }`}
            >
              <Server className="w-3 h-3 text-amber-200" />
              Provider B (Slow / Flaky / Out-of-Order)
            </button>
          </div>
        </div>

        {/* Action Trigger */}
        <div className="flex items-end">
          <button
            onClick={onTriggerCycle}
            disabled={isTriggering}
            className="flex items-center justify-center gap-2 w-full lg:w-auto px-5 py-2.5 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white text-xs font-semibold rounded-lg shadow-lg shadow-blue-500/10 transition-all disabled:opacity-50"
          >
            <Play className={`w-3.5 h-3.5 ${isTriggering ? 'animate-spin' : ''}`} />
            <span>{isTriggering ? 'Running Cycle...' : 'Run Single Dialing Cycle'}</span>
          </button>
        </div>

      </div>
    </div>
  );
};
