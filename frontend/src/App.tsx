import React, { useState, useEffect, useRef } from 'react';
import {
  fetchMetrics,
  fetchAgents,
  fetchActiveCalls,
  fetchSafetyAudits,
  updateCampaignSettings,
  triggerDialerCycle,
  setSimulationScenario,
  tickSimulation,
  injectFailure,
  triggerRecovery,
  resetSimulation
} from './api/client';
import { SystemMetrics, Agent, Call, SafetyDecisionAudit, DialingMode, ProviderType } from './types';
import { MetricsBar } from './components/MetricsBar';
import { DialingControlPanel } from './components/DialingControlPanel';
import { SafetyAuditPanel } from './components/SafetyAuditPanel';
import { AgentGrid } from './components/AgentGrid';
import { LiveCallsTable } from './components/LiveCallsTable';
import { SimulationControls } from './components/SimulationControls';
import { FailureInjectionPanel } from './components/FailureInjectionPanel';
import { Radio, RefreshCw } from 'lucide-react';

export const App: React.FC = () => {
  const [metrics, setMetrics] = useState<SystemMetrics | null>(null);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [activeCalls, setActiveCalls] = useState<Call[]>([]);
  const [safetyAudits, setSafetyAudits] = useState<SafetyDecisionAudit[]>([]);
  const [currentScenario, setCurrentScenario] = useState<string>('SCENARIO_B');
  const [isRunningAutoTick, setIsRunningAutoTick] = useState<boolean>(false);
  const [isTriggering, setIsTriggering] = useState<boolean>(false);
  const [lastRefreshed, setLastRefreshed] = useState<Date>(new Date());

  const autoTickIntervalRef = useRef<any>(null);

  // Poll system data
  const refreshAllData = async () => {
    try {
      const [m, a, c, s] = await Promise.all([
        fetchMetrics(),
        fetchAgents(),
        fetchActiveCalls(),
        fetchSafetyAudits(15)
      ]);
      setMetrics(m);
      setAgents(a);
      setActiveCalls(c);
      setSafetyAudits(s);
      setLastRefreshed(new Date());
    } catch (err) {
      console.error('Polling error:', err);
    }
  };

  useEffect(() => {
    refreshAllData();
    const interval = setInterval(refreshAllData, 1500);
    return () => clearInterval(interval);
  }, []);

  // Handle Auto-Tick Simulation Loop
  useEffect(() => {
    if (isRunningAutoTick) {
      autoTickIntervalRef.current = setInterval(async () => {
        try {
          await tickSimulation(1);
          await refreshAllData();
        } catch (e) {
          console.error('Auto-tick error:', e);
        }
      }, 1200);
    } else {
      if (autoTickIntervalRef.current) {
        clearInterval(autoTickIntervalRef.current);
      }
    }
    return () => {
      if (autoTickIntervalRef.current) clearInterval(autoTickIntervalRef.current);
    };
  }, [isRunningAutoTick]);

  const handleUpdateMode = async (mode: DialingMode) => {
    await updateCampaignSettings(mode, undefined);
    await refreshAllData();
  };

  const handleUpdateProvider = async (provider: ProviderType) => {
    await updateCampaignSettings(undefined, provider);
    await refreshAllData();
  };

  const handleTriggerCycle = async () => {
    setIsTriggering(true);
    try {
      await triggerDialerCycle();
      await refreshAllData();
    } finally {
      setIsTriggering(false);
    }
  };

  const handleSelectScenario = async (scenario: string) => {
    setCurrentScenario(scenario);
    await setSimulationScenario(scenario);
    await refreshAllData();
  };

  const handleStepTick = async (ticks: number) => {
    await tickSimulation(ticks);
    await refreshAllData();
  };

  const handleReset = async () => {
    setIsRunningAutoTick(false);
    await resetSimulation(60, 250);
    setCurrentScenario('SCENARIO_B');
    await refreshAllData();
  };

  return (
    <div className="min-h-screen bg-[#0A0E17] text-gray-100 flex flex-col font-sans">
      {/* Top Header */}
      <header className="border-b border-gray-800 bg-[#0D1321] sticky top-0 z-50 px-6 py-3.5 flex items-center justify-between shadow-md">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-gradient-to-tr from-blue-600 to-indigo-500 flex items-center justify-center shadow-lg shadow-blue-500/20 text-white font-black text-lg">
            CR
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-base font-bold text-white tracking-tight">
                CredResolve SmartDialer
              </h1>
              <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-blue-500/15 text-blue-400 border border-blue-500/30">
                PROTOTYPE v1.0
              </span>
            </div>
            <p className="text-xs text-gray-400">
              High-Throughput Safe Collections Dialer & Autonomous Safety Controller
            </p>
          </div>
        </div>

        {/* Live Status Indicators */}
        <div className="flex items-center gap-4 text-xs font-mono">
          <div className="hidden sm:flex items-center gap-2 bg-[#0A0E17] px-3 py-1.5 rounded-lg border border-gray-800">
            <Radio className="w-3.5 h-3.5 text-emerald-400 animate-pulse" />
            <span className="text-gray-300">Active Engine:</span>
            <span className="font-bold text-white">
              {metrics?.current_dialing_mode || 'PROGRESSIVE'}
            </span>
          </div>

          <button
            onClick={refreshAllData}
            className="flex items-center gap-1.5 text-gray-400 hover:text-white transition-colors bg-[#0A0E17] p-1.5 rounded-lg border border-gray-800"
            title="Manual sync"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span className="text-[11px] hidden md:inline">
              {lastRefreshed.toLocaleTimeString()}
            </span>
          </button>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-4 sm:p-6 space-y-5">
        {/* 1. Primary Metrics KPI Bar */}
        <MetricsBar metrics={metrics} />

        {/* 2. Dialing Controls (Mode & Provider Selectors) */}
        <DialingControlPanel
          currentMode={metrics?.current_dialing_mode || 'PROGRESSIVE'}
          currentProvider={metrics?.active_provider || 'PROVIDER_A'}
          onUpdateMode={handleUpdateMode}
          onUpdateProvider={handleUpdateProvider}
          onTriggerCycle={handleTriggerCycle}
          isTriggering={isTriggering}
        />

        {/* 3. Independent Safety Controller Audit Panel */}
        <SafetyAuditPanel
          lastDecision={metrics?.last_safety_decision || null}
          history={safetyAudits}
        />

        {/* 4. Live Agent Matrix & Active Calls */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          <AgentGrid agents={agents} />
          <LiveCallsTable calls={activeCalls} />
        </div>

        {/* 5. Simulation Scenarios & Failure Injection Controls */}
        <SimulationControls
          currentScenario={currentScenario}
          onSelectScenario={handleSelectScenario}
          isRunningAutoTick={isRunningAutoTick}
          onToggleAutoTick={() => setIsRunningAutoTick(!isRunningAutoTick)}
          onStepTick={handleStepTick}
          onReset={handleReset}
        />

        <FailureInjectionPanel
          onInject={injectFailure}
          onTriggerRecovery={triggerRecovery}
        />
      </main>

      {/* Footer */}
      <footer className="border-t border-gray-800/80 bg-[#0D1321] py-4 px-6 text-center text-xs text-gray-500 font-mono">
        CredResolve SmartDialer Hiring Assignment 2026 • Built with FastAPI, SQLite WAL, React & TypeScript
      </footer>
    </div>
  );
};
