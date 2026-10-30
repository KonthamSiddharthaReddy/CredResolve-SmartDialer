import { SystemMetrics, Agent, Call, SafetyDecisionAudit, DialingMode, ProviderType } from '../types';

const API_BASE = '/api/v1';

export async function fetchMetrics(): Promise<SystemMetrics> {
  const res = await fetch(`${API_BASE}/dialer/metrics?campaign_id=1`);
  if (!res.ok) throw new Error('Failed to fetch system metrics');
  return res.json();
}

export async function fetchAgents(status?: string): Promise<Agent[]> {
  const url = status ? `${API_BASE}/agents?status=${status}&limit=120` : `${API_BASE}/agents?limit=120`;
  const res = await fetch(url);
  if (!res.ok) throw new Error('Failed to fetch agents');
  return res.json();
}

export async function fetchActiveCalls(): Promise<Call[]> {
  const res = await fetch(`${API_BASE}/calls/active?limit=50`);
  if (!res.ok) throw new Error('Failed to fetch active calls');
  return res.json();
}

export async function fetchSafetyAudits(limit: number = 20): Promise<SafetyDecisionAudit[]> {
  const res = await fetch(`${API_BASE}/dialer/safety-audits?campaign_id=1&limit=${limit}`);
  if (!res.ok) throw new Error('Failed to fetch safety audits');
  return res.json();
}

export async function updateCampaignSettings(
  dialingMode?: DialingMode,
  providerType?: ProviderType
): Promise<any> {
  const body: any = {};
  if (dialingMode) body.dialing_mode = dialingMode;
  if (providerType) body.provider_type = providerType;

  const res = await fetch(`${API_BASE}/campaigns/1`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });
  if (!res.ok) throw new Error('Failed to update campaign settings');
  return res.json();
}

export async function triggerDialerCycle(): Promise<any> {
  const res = await fetch(`${API_BASE}/dialer/cycle?campaign_id=1`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to trigger dialer cycle');
  return res.json();
}

export async function setSimulationScenario(scenarioName: string): Promise<any> {
  const res = await fetch(`${API_BASE}/simulation/scenario?name=${scenarioName}&campaign_id=1`, {
    method: 'POST'
  });
  if (!res.ok) throw new Error('Failed to set scenario');
  return res.json();
}

export async function tickSimulation(ticks: number = 1): Promise<any> {
  const res = await fetch(`${API_BASE}/simulation/tick?ticks=${ticks}&campaign_id=1`, {
    method: 'POST'
  });
  if (!res.ok) throw new Error('Failed to execute simulation tick');
  return res.json();
}

export async function injectFailure(type: string, params?: Record<string, any>): Promise<any> {
  const res = await fetch(`${API_BASE}/simulation/failure`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ type, params })
  });
  if (!res.ok) throw new Error(`Failed to inject failure: ${type}`);
  return res.json();
}

export async function triggerRecovery(): Promise<any> {
  const res = await fetch(`${API_BASE}/simulation/recover`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to trigger recovery reaper');
  return res.json();
}

export async function resetSimulation(agents: number = 60, borrowers: number = 250): Promise<any> {
  const res = await fetch(`${API_BASE}/simulation/reset?num_agents=${agents}&num_borrowers=${borrowers}`, {
    method: 'POST'
  });
  if (!res.ok) throw new Error('Failed to reset simulation');
  return res.json();
}
