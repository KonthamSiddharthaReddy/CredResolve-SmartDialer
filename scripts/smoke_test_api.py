import sys
import urllib.request
import json

def test_api_flows():
    print("[SMOKE TEST 1] Verifying backend health...")
    req = urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=5)
    health = json.loads(req.read().decode())
    assert health.get("status") == "healthy", f"Health status unexpected: {health}"
    print(f" -> Backend Health: {health}")

    print("[SMOKE TEST 2] Verifying frontend dev server...")
    req_fe = urllib.request.urlopen("http://localhost:3000", timeout=5)
    assert req_fe.status == 200, f"Frontend returned status: {req_fe.status}"
    fe_html = req_fe.read().decode()
    assert "<title>" in fe_html, "Frontend HTML missing <title>"
    print(f" -> Frontend HTTP 200 OK (HTML size: {len(fe_html)} bytes)")

    print("[SMOKE TEST 3] Testing Progressive Dialing Mode...")
    # Set campaign to Progressive
    patch_req = urllib.request.Request(
        "http://127.0.0.1:8000/api/v1/campaigns/1",
        data=json.dumps({"dialing_mode": "PROGRESSIVE"}).encode(),
        headers={"Content-Type": "application/json"},
        method="PATCH"
    )
    camp = json.loads(urllib.request.urlopen(patch_req, timeout=5).read().decode())
    assert camp["dialing_mode"] == "PROGRESSIVE", f"Expected PROGRESSIVE, got {camp['dialing_mode']}"

    # Trigger cycle
    post_req = urllib.request.Request("http://127.0.0.1:8000/api/v1/dialer/cycle?campaign_id=1", method="POST")
    cycle_prog = json.loads(urllib.request.urlopen(post_req, timeout=5).read().decode())
    assert cycle_prog.get("status") == "success"
    assert cycle_prog.get("mode") == "PROGRESSIVE"
    print(f" -> Progressive Cycle: {cycle_prog['safety_decision']} | Approved: {cycle_prog['approved_calls']} | Initiated: {cycle_prog['initiated_calls_count']}")

    print("[SMOKE TEST 4] Testing Predictive Dialing Mode...")
    # Set campaign to Predictive
    patch_pred = urllib.request.Request(
        "http://127.0.0.1:8000/api/v1/campaigns/1",
        data=json.dumps({"dialing_mode": "PREDICTIVE"}).encode(),
        headers={"Content-Type": "application/json"},
        method="PATCH"
    )
    camp_pred = json.loads(urllib.request.urlopen(patch_pred, timeout=5).read().decode())
    assert camp_pred["dialing_mode"] == "PREDICTIVE", f"Expected PREDICTIVE, got {camp_pred['dialing_mode']}"

    # Trigger cycle
    cycle_pred = json.loads(urllib.request.urlopen(post_req, timeout=5).read().decode())
    assert cycle_pred.get("status") == "success"
    assert cycle_pred.get("mode") == "PREDICTIVE"
    print(f" -> Predictive Cycle: {cycle_pred['safety_decision']} | Approved: {cycle_pred['approved_calls']} | Initiated: {cycle_pred['initiated_calls_count']}")

    print("[SMOKE TEST 5] Checking System Metrics API...")
    req_m = urllib.request.urlopen("http://127.0.0.1:8000/api/v1/dialer/metrics?campaign_id=1", timeout=5)
    metrics = json.loads(req_m.read().decode())
    print(f" -> System Metrics: Agents Available={metrics['available_agents']}, Total={metrics['total_agents']}, Mode={metrics['current_dialing_mode']}")

    print("\nALL SMOKE TESTS PASSED!")

if __name__ == "__main__":
    test_api_flows()
