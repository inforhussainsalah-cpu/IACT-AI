import os
import ssl
import json
import urllib.request
import urllib.error
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

app = FastAPI(title="IACT-AI + Gemini", version="0.2.4")

class QueryRequest(BaseModel):
    prompt: str
    evidence_level: str = "E0"
    permission_level: str = "L0"

@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <!DOCTYPE html>
    <html lang="dv" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>IACT-AI + Gemini</title>
        <style>
            body { font-family: 'Faruma', sans-serif; background: #0f172a; color: #f8fafc; padding: 20px; max-width: 720px; margin: auto; }
            .card { background: #1e293b; padding: 20px; border-radius: 12px; margin-bottom: 16px; border: 1px solid #334155; }
            textarea, select, button { width: 100%; padding: 12px; margin-top: 8px; border-radius: 8px; border: 1px solid #475569; background: #0f172a; color: white; font-size: 16px; box-sizing: border-box; }
            button { background: #2563eb; border: none; font-weight: bold; cursor: pointer; margin-top: 16px; }
            .badge { display: inline-block; padding: 4px 10px; border-radius: 6px; font-weight: bold; }
            .PASS { background: #16a34a; } .REVIEW { background: #ca8a04; } .RESTRICT { background: #dc2626; } .UNKNOWN { background: #475569; }
            .ai-box { background: #0f172a; padding: 14px; border-radius: 8px; border-right: 4px solid #3b82f6; margin-top: 12px; white-space: pre-wrap; line-height: 1.7; }
        </style>
    </head>
    <body>
        <h2>🧠 IACT-AI + Gemini (ދިވެހި އިންޓަފޭސް)</h2>
        <div class="card">
            <label>ސުވާލު ނުވަތަ ދިރާސާ މަޢުޟޫޢު ލިޔުއްވާ:</label>
            <textarea id="prompt" rows="3" placeholder="މިތަނުގައި ތާނައިން ނުވަތަ އިނގިރޭސިން ލިޔުއްވާ..."></textarea>
            <label>ހެކީގެ ފެންވަރު (Evidence Level):</label>
            <select id="evidence">
                <option value="E0">E0 = ޚިޔާލީ ހުށަހެޅުން (Conceptual)</option>
                <option value="E1">E1 = އޮޕަރޭޝަނަލް ހައިޕޮތިސިސް</option>
                <option value="E2">E2 = ޕައިލެޓް / ފީޒިބިލިޓީ ހެކި</option>
                <option value="E3">E3 = ކަށަވަރުކުރެވިފައިވާ ހެކި</option>
                <option value="E4">E4 = ކޮމްޕެޓިބަލް ރެޕްލިކޭޝަން</option>
                <option value="E5">E5 = މިނިވަން ވެލިޑޭޝަން</option>
            </select>
            <label>ހުއްދައިގެ ފެންވަރު (Permission Level):</label>
            <select id="permission">
                <option value="L0">L0 = READ (ކިޔުން)</option>
                <option value="L1">L1 = CREATE (އުފެއްދުން)</option>
                <option value="L2">L2 = PROPOSE (ހުށަހެޅުން)</option>
                <option value="L3">L3 = ACT (ޢަމަލުކުރުން)</option>
                <option value="L4">L4 = HIGH-IMPACT ACTION</option>
            </select>
            <button id="btn" onclick="runIACT()">IACT-AI + Gemini ހިންގާލާ</button>
        </div>
        <div id="result" class="card" style="display:none;"></div>
        <script>
            async function runIACT() {
                const btn = document.getElementById('btn');
                const box = document.getElementById('result');
                btn.innerText = "ޖަވާބު ހޯދަނީ...";
                btn.disabled = true;
                try {
                    const res = await fetch('/api/evaluate', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({
                            prompt: document.getElementById('prompt').value,
                            evidence_level: document.getElementById('evidence').value,
                            permission_level: document.getElementById('permission').value
                        })
                    });
                    const data = await res.json();
                    box.style.display = 'block';
                    box.innerHTML = `<h3>ގަވަރނަންސް ނަތީޖާ: <span class="badge ${data.governance}">${data.governance}</span></h3>
                        <p><b>އުޞޫލު:</b> ${data.principle}</p>
                        <p><b>ޙާލަތު:</b> ${data.message}</p>
                        <div class="ai-box"><b>Gemini ގެ ތަޙުލީލު:</b><br>${data.ai_response}</div>`;
                } catch (err) {
                    box.style.display = 'block';
                    box.innerHTML = `<p style="color:#f87171;"><b>ގުޅުން ކެނޑިއްޖެ:</b> ${err.message}</p>`;
                } finally {
                    btn.innerText = "IACT-AI + Gemini ހިންގާލާ";
                    btn.disabled = false;
                }
            }
        </script>
    </body>
    </html>
    """

@app.post("/api/evaluate")
def evaluate(req: QueryRequest):
    if not req.prompt.strip():
        return {
            "governance": "UNKNOWN",
            "principle": "CLAIM STRENGTH <= EVIDENCE STRENGTH",
            "message": "ސުވާލެއް ނުވަތަ މަޢުލޫމާތެއް ދެއްވާފައި ނުވާތީ ނިންމުމެއް ނުނިންމޭނެއެވެ.",
            "ai_response": "ސުވާލެއް ލިޔުއްވުމަށްފަހު އަލުން މަސައްކަތްކޮށްލައްވާ."
        }
    elif req.permission_level in ["L3", "L4"]:
        return {
            "governance": "RESTRICT",
            "principle": "CLAIM STRENGTH <= EVIDENCE STRENGTH",
            "message": "No Self-Approval އުޞޫލުގެ ދަށުން L3/L4 ޢަމަލުތަކަށް އިންސާނީ ހުއްދަ ބޭނުންވެއެވެ.",
            "ai_response": "ހުއްދަ ހިފެހެއްޓިފައިވާތީ Gemini އިން ޢަމަލީ ފިޔަވަޅެއް ނާޅާނެއެވެ."
        }

    gov = "REVIEW" if req.evidence_level in ["E0", "E1"] else "PASS"
    msg = (
        f"ހެކީގެ ފެންވަރު ({req.evidence_level}) ދަށްވުމުން އިތުރު ދިރާސާ ބޭނުންވެއެވެ."
        if gov == "REVIEW"
        else f"ހެކީގެ ފެންވަރު ({req.evidence_level}) އަދި ހުއްދަ ({req.permission_level}) ޝަރުޠު ހަމަވެއެވެ."
    )

    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        ai_text = "GEMINI_API_KEY ސެޓްކޮށްފައި ނެތެވެ."
    else:
        ctx = ssl._create_unverified_context()
        flash_models = []
        try:
            list_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
            with urllib.request.urlopen(list_url, timeout=6, context=ctx) as resp:
                m_data = json.loads(resp.read().decode("utf-8"))
                for m in m_data.get("models", []):
                    if "generateContent" in m.get("supportedGenerationMethods", []):
                        name = m["name"].replace("models/", "")
                        if "flash" in name and "embedding" not in name:
                            flash_models.append(name)
        except Exception:
            pass

        if not flash_models:
            flash_models = ["gemini-3.8-flash", "gemini-2.0-flash"]
        flash_models = flash_models[:3]

        system_instruction = (
            f"You are IACT-AI, an evidence-governed scientific assistant. "
            f"Enforce: CLAIM STRENGTH <= EVIDENCE STRENGTH. "
            f"Current Evidence Level: {req.evidence_level}, Governance State: {gov}. "
            f"Respond concisely in the same language as the user's prompt (Dhivehi/Thaana if written in Dhivehi)."
        )
        payload = {
            "generationConfig": {"thinkingConfig": {"thinkingBudget": 0}},
            "contents": [{
                "parts": [{"text": f"{system_instruction}\n\nUser Prompt: {req.prompt}"}]
            }]
        }
        ai_text = None
        last_err = ""

        for model in flash_models:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
                request = urllib.request.Request(
                    url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST"
                )
                with urllib.request.urlopen(request, timeout=10, context=ctx) as resp:
                    result = json.loads(resp.read().decode("utf-8"))
                    ans = result["candidates"][0]["content"]["parts"][0]["text"]
                    ai_text = f"[{model}]\n{ans}"
                    break
            except urllib.error.HTTPError as e:
                err_body = e.read().decode("utf-8", errors="ignore")
                last_err = f"{model} ({e.code}): {err_body[:150]}"
            except Exception as e:
                last_err = f"{model}: {str(e)}"

        if not ai_text:
            ai_text = f"ޓެސްޓުކުރެވުނު މޮޑެލްތައް ({', '.join(flash_models)}):\nއެރާ: {last_err}"

    return {
        "governance": gov,
        "principle": "CLAIM STRENGTH <= EVIDENCE STRENGTH",
        "message": msg,
        "ai_response": ai_text
    }
