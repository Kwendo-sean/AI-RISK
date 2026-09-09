import http from "k6/http";
import { check, sleep } from "k6";
import { Trend, Rate } from "k6/metrics";

const BASE = __ENV.BASE_URL || "http://127.0.0.1:8000";
const apiLatency = new Trend("career_api_latency", true);
const journeyFailures = new Rate("journey_failures");

export const options = {
  scenarios: {
    progressive_journey: {
      executor: "ramping-vus",
      startVUs: 0,
      stages: [
        { duration: __ENV.STAGE_100 || "2m", target: 100 },
        { duration: __ENV.HOLD_100 || "3m", target: 100 },
        { duration: __ENV.STAGE_500 || "3m", target: 500 },
        { duration: __ENV.HOLD_500 || "3m", target: 500 },
        { duration: __ENV.STAGE_1000 || "4m", target: 1000 },
        { duration: __ENV.HOLD_1000 || "4m", target: 1000 },
        { duration: __ENV.STAGE_2000 || "5m", target: 2000 },
        { duration: __ENV.HOLD_2000 || "5m", target: 2000 },
        { duration: "2m", target: 0 }
      ],
      gracefulRampDown: "45s"
    }
  },
  thresholds: {
    http_req_failed: ["rate<0.01"],
    http_req_duration: ["p(95)<500"],
    career_api_latency: ["p(95)<500"],
    journey_failures: ["rate<0.01"]
  }
};

function jsonRequest(method, path, body, token) {
  const params = { headers: { "Content-Type": "application/json" }, tags: { endpoint: path.replace(/[0-9a-f-]{20,}/g, ":id") } };
  if (token) params.headers["X-Session-Token"] = token;
  const response = http.request(method, `${BASE}${path}`, body === null ? null : JSON.stringify(body), params);
  apiLatency.add(response.timings.duration);
  return response;
}

export default function () {
  let failed = false;
  let response = http.get(`${BASE}/`);
  failed ||= !check(response, { "landing loaded": r => r.status === 200 });
  sleep(Math.random() * 1.2 + 0.4);

  response = jsonRequest("GET", "/api/v2/careers?q=mechanic&limit=8", null);
  failed ||= !check(response, { "career search worked": r => r.status === 200 && r.json("careers.0.id") });
  const careerId = response.json("careers.0.id") || "auto-mechanic";
  sleep(Math.random() * 1.5 + 0.5);

  response = jsonRequest("POST", "/api/v2/profiles", {
    first_name: "LoadUser",
    career_id: careerId,
    custom_career: null,
    career_stage: "Early-career",
    industry: "Skilled Trades",
    region: "Test region",
    education_level: null,
    years_experience: 3
  });
  failed ||= !check(response, { "profile created": r => r.status === 201 });
  if (response.status !== 201) { journeyFailures.add(true); return; }
  const sid = response.json("session_id"), token = response.json("access_token");

  response = jsonRequest("POST", `/api/v2/profiles/${sid}/assessments`, {}, token);
  failed ||= !check(response, { "assessment started": r => r.status === 201 });
  if (response.status !== 201) { journeyFailures.add(true); return; }
  const aid = response.json("assessment_id");
  let next = response.json("next_question");
  while (next) {
    sleep(Math.random() * 0.5 + 0.15);
    response = jsonRequest("POST", `/api/v2/profiles/${sid}/assessments/${aid}/answers`, { question_id: next.id, answer_index: Math.floor(Math.random() * 5) }, token);
    if (response.status !== 200) { failed = true; break; }
    next = response.json("next_question");
  }
  if (!failed) {
    response = jsonRequest("POST", `/api/v2/profiles/${sid}/assessments/${aid}/complete`, {}, token);
    failed ||= !check(response, { "assessment completed": r => r.status === 200 && r.json("result.dimensions") });
    response = jsonRequest("GET", `/api/v2/profiles/${sid}/assessments/${aid}`, null, token);
    failed ||= !check(response, { "result viewed": r => r.status === 200 && r.json("status") === "complete" });
    response = jsonRequest("POST", `/api/v2/profiles/${sid}/assessments/${aid}/game-events`, { event_id: `load-${__VU}-${__ITER}-${aid}`.slice(0, 80), event_type: "skill_opened", payload: { skill_id: "workflow_mapping" } }, token);
    failed ||= response.status !== 200;
  }
  jsonRequest("DELETE", `/api/v2/profiles/${sid}`, null, token);
  journeyFailures.add(failed);
  sleep(Math.random() * 2 + 0.5);
}

