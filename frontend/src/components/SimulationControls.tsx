import React from 'react';
import { Play, Pause, FastForward, RotateCcw } from 'lucide-react';

interface SimulationControlsProps {
  currentScenario: string;
  onSelectScenario: (scenario: string) => void;
  isRunningAutoTick: boolean;
  onToggleAutoTick: () => void;
  onStepTick: (ticks: number) => void;
  onReset: () => void;
}

export const SimulationControls: React.FC<SimulationControlsProps> = ({
  currentScenario,
  onSelectScenario,
  isRunningAutoTick,
  onToggleAutoTick,
  onStepTick,
  onReset
}) => {
  const scenarios = [
    { id: 'SCENARIO_A', label: 'Scenario A', desc: '20% Ans, 120s Talk' },
    { id: 'SCENARIO_B', label: 'Scenario B', desc: '50% Ans, 90s Talk' },
    { id: 'SCENARIO_C', label: 'Scenario C', desc: '70% Ans, 180s Talk' },
    { id: 'SCENARIO_D', label: 'Scenario D', desc: 'Dynamic Volatility' },
  ];

  return (
    <div className="bg-[#111827] border border-gray-800 rounded-xl p-5 flex flex-col gap-4">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-gray-800/80 pb-3">
        <div>
          <h2 className="text-sm font-bold text-white tracking-wide">
            Simulation & Scenarios Engine
          </h2>
          <p className="text-xs text-gray-400">
            Driven by 10x accelerated queue progression & stochastic answer models
          </p>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-2">
          <button
            onClick={onToggleAutoTick}
            className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all ${
              isRunningAutoTick
                ? 'bg-amber-600 hover:bg-amber-500 text-white animate-pulse'
                : 'bg-emerald-600 hover:bg-emerald-500 text-white'
            }`}
          >
            {isRunningAutoTick ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
            {isRunningAutoTick ? 'Pause Engine' : 'Auto-Tick Live'}
          </button>

          <button
            onClick={() => onStepTick(1)}
            disabled={isRunningAutoTick}
            className="flex items-center gap-1 px-3 py-1.5 bg-gray-800 hover:bg-gray-700 text-gray-200 text-xs font-medium rounded-lg transition-all disabled:opacity-40"
          >
            Step 1x
          </button>

          <button
            onClick={() => onStepTick(5)}
            disabled={isRunningAutoTick}
            className="flex items-center gap-1 px-3 py-1.5 bg-gray-800 hover:bg-gray-700 text-gray-200 text-xs font-medium rounded-lg transition-all disabled:opacity-40"
          >
            <FastForward className="w-3.5 h-3.5" />
            Step 5x
          </button>

          <button
            onClick={onReset}
            className="flex items-center gap-1 px-3 py-1.5 bg-red-950/40 hover:bg-red-900/60 border border-red-800 text-red-300 text-xs font-medium rounded-lg transition-all"
            title="Reset simulation to initial clean state"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            Reset
          </button>
        </div>
      </div>

      {/* Scenario Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {scenarios.map(sc => (
          <button
            key={sc.id}
            onClick={() => onSelectScenario(sc.id)}
            className={`p-3 rounded-lg border text-left transition-all ${
              currentScenario === sc.id
                ? 'bg-blue-600/15 border-blue-500 text-white shadow-sm'
                : 'bg-[#0A0E17] border-gray-800 text-gray-400 hover:bg-gray-800/40 hover:text-gray-200'
            }`}
          >
            <span className="text-xs font-bold font-mono block text-white">{sc.label}</span>
            <span className="text-[11px] font-mono text-gray-400 block mt-0.5">{sc.desc}</span>
          </button>
        ))}
      </div>
    </div>
  );
};
