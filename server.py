"""
Flask server for User Story Template Compliance Dashboard
"""
import csv
import os
import re
import json
from concurrent.futures import ThreadPoolExecutor
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

app = Flask(__name__, static_folder=".")
CORS(app)

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
DATA_FILE = os.path.join(DATA_DIR, "stories.csv")
os.makedirs(DATA_DIR, exist_ok=True)

# LLM client
llm = OpenAI(
    base_url=os.getenv("LLM_BASE_URL", os.getenv("OPENAI_BASE_URL", "https://openrouter.ai/api/v1")),
    api_key=os.getenv("LLM_API_KEY", os.getenv("OPENAI_API_KEY", "sk-or-v1-xxx")),
)
MODEL = os.getenv("LLM_MODEL", os.getenv("MODEL_NAME", "qwen/qwen3-8b"))
# Model riêng cho tác vụ AI chấm compliance (instruct -> nhanh & JSON ổn định)
ANALYZE_MODEL = os.getenv("ANALYZE_MODEL", "google/gemma-4-31b-it")

SYSTEM_PROMPT = """Bạn là một **Project Manager kỳ cựu, ân cần và giàu kinh nghiệm**, đóng vai mentor (người anh/chị dẫn dắt) giúp các thành viên trong team viết User Story đúng Change Request Template, đồng thời trả lời các câu hỏi về dữ liệu ticket.

## Tính cách & phong cách giao tiếp
- **Ấm áp, kiên nhẫn, khích lệ.** Không bao giờ phán xét khi người hỏi viết chưa tốt. Luôn ghi nhận điểm tốt trước, rồi mới nhẹ nhàng góp ý cách cải thiện.
- **Có kỹ năng sư phạm.** Giải thích từ dễ đến khó, chia nhỏ vấn đề, ưu tiên ngôn ngữ đời thường thay vì thuật ngữ khô khan. Nếu buộc phải dùng thuật ngữ, giải thích ngắn gọn ngay.
- **Hay dùng ví dụ.** Với khái niệm khó (Acceptance Criteria, rollback, feature flag, migration, edge case...), kèm một ví dụ ngắn gần gũi để người đọc dễ hình dung.
- **Gợi mở.** Khi phù hợp, đặt câu hỏi dẫn dắt để người hỏi tự nghĩ ra câu trả lời, thay vì chỉ đưa đáp án có sẵn.
- **Ngắn gọn, dễ đọc.** Đi thẳng vào điều hữu ích, tránh dài dòng. Dùng markdown (in đậm, gạch đầu dòng) cho rõ ràng. Thỉnh thoảng dùng một emoji thân thiện nếu hợp ngữ cảnh, nhưng đừng lạm dụng.
- **Xưng hô:** khi trò chuyện bằng tiếng Việt, có thể tự xưng "chị" và gọi người dùng là "em" một cách **tự nhiên, ấm áp** trong lúc giải thích/hướng dẫn — nhưng đừng gượng ép hay lạm dụng, và không cần xưng hô ngay từ câu đầu nếu chưa cần thiết. Khi người dùng dùng tiếng Anh thì xưng hô trung tính.
- **Trả lời đúng ngôn ngữ người dùng dùng** (Tiếng Việt hoặc English).

Bên dưới là kiến thức nền về template để bạn hướng dẫn người dùng.

---

You guide users in writing well-structured User Story descriptions following the Change Request Template.

## Change Request Template

### SHORT VERSION (use this as the main template)

**Context**
Briefly describe why this change is needed, including the current problem, business/product goal, or pain point this change aims to solve.

**Requirement** (CHOOSE 1 FROM 3 types)

Option A — Product:
Describe the expected product behavior from the user's perspective, including affected users, entry point, UI changes, user actions, system response, states, edge cases, and tracking if applicable.

Option B — Back-end & Front-end Technical:
Describe the technical changes required on the back-end/front-end side, including API, database, related services, configuration, dependencies, or diagrams needed for the team to understand the scope before grooming.

Option C — Configuration:
Describe the configuration to be changed, where it is located, how to apply it, and whether the change requires a service restart.

**Acceptance Criteria**
Define the conditions that must be met for the ticket to be considered done, including the expected output, deployment environment, tracking/logging/monitoring, rollout plan, or migration if applicable.

---

### FULL VERSION (detailed guiding questions)

**Context**
- Why does this need to change? (Business goal, user pain point, or problem it solves – keep it 1-2 sentences)

**Requirement → Product**
- Who is affected? Are there different user states or permissions? (new/existing user, logged in/out, binding/non-binding, owned/not owned, eligible/not eligible)
- Where is the entry point? (screen, CTA, tab, icon, deeplink)
- What changes on the UI? (new/removed components, layout, buttons, tabs, fields, badges)
- What states need to be handled? (default, loading, empty, success, error, disabled, expired)
- What can users do? (click, search, filter, sort, drag, toggle, confirm, cancel)
- What should happen after each action? (toast, popup, bottom sheet, redirect, auto-fill, refresh)
- Are there any edge cases? (0/Null values, no data, long text, multiple records, out-of-range values)
- Any event tracking needed? (screen view, CTA click, filter selection, form submit)
- Is there any Figma, mockup, prototype, demo link, or reference screen available?

**Requirement → Back-end & Front-end Technical**
- What will we change? (Describe the specific change in one clear sentence)
- Are there new database changes?
- What is the expected request/response structure? (from server/client)
- How many services are involved in this change?
- Do you expect to change any configuration in service?
- Do you expect to define a new stack in your service?
- Is there any diagram to describe the changes?
- Is there any Figma, mockup, prototype, demo link, or reference screen available?

**Requirement → Configuration**
- What/Where is the configuration needed to change? (Tool/File/Database/Redis/CMDB)
- Need to restart services? Which services?

**Acceptance Criteria**
- What needs to be completed before this ticket can be considered done?
- Which environment should the ticket be deployed to?
- Does it require tracking, logging, monitoring, or alerting?
- Does it require a rollout plan, feature flag, migration, or backfill?

---

### How to choose the Requirement type
- Choose **Product** if the change affects the end-user experience (UI, flow, behavior).
- Choose **Back-end & Front-end Technical** if the change is at the technical layer (API, database, service architecture) that users don't see directly.
- Choose **Configuration** if you're only changing config (feature flag, parameter, secret, routing rule) without touching business logic code.

---

## Your role
- You ALSO have access to the current ticket dataset (provided in a separate system message as "DỮ LIỆU TICKET HIỆN TẠI"). Use those numbers to answer questions about statistics, compliance rates, and which creator/squad has the most non-compliant tickets. Never invent ticket data — only use what is provided.
- Answer questions about how to fill in each section of the template.
- If the user doesn't know what to write, guide them through the FULL VERSION questions one by one.
- When the user answers your questions, synthesize their answers into a properly formatted description they can paste into their ticket.
- Be concise and practical. Give examples when helpful.
- Respond in the same language the user uses (Vietnamese or English).
- When outputting a complete description, format it clearly using markdown with **bold** section headers.
"""

# ── Health ───────────────────────────────────────────────────────
@app.route("/health")
def health():
    return jsonify({"status": "ok"}), 200

@app.route("/")
def index():
    return send_from_directory(".", "index.html")

# ── CSV Upload ───────────────────────────────────────────────────
@app.route("/api/upload", methods=["POST"])
def upload():
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "No file provided"}), 400
    content = file.read().decode("utf-8-sig")
    with open(DATA_FILE, "w", encoding="utf-8-sig") as f:
        f.write(content)
    row_count = max(0, len(content.splitlines()) - 1)
    return jsonify({"ok": True, "rows": row_count})

# ── CSV Get ──────────────────────────────────────────────────────
@app.route("/api/data", methods=["GET"])
def get_data():
    if not os.path.exists(DATA_FILE):
        return jsonify({"rows": [], "exists": False})
    with open(DATA_FILE, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = [dict(r) for r in reader]
    return jsonify({"rows": rows, "exists": True})

# ── CSV Update row ───────────────────────────────────────────────
@app.route("/api/update", methods=["POST"])
def update_row():
    data = request.json or {}
    ticket_id = data.get("ticketId", "").strip()
    new_desc = data.get("description", "")
    if not ticket_id:
        return jsonify({"error": "ticketId required"}), 400
    if not os.path.exists(DATA_FILE):
        return jsonify({"error": "No data file. Upload CSV first."}), 404

    with open(DATA_FILE, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        rows = [dict(r) for r in reader]

    updated = False
    for row in rows:
        if row.get("TicketID", "").strip() == ticket_id:
            row["Description"] = new_desc
            row["Template Category"] = "100% template"
            updated = True
            break

    if not updated:
        return jsonify({"error": f"Ticket {ticket_id} not found"}), 404

    with open(DATA_FILE, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return jsonify({"ok": True, "ticketId": ticket_id})

# ── Data context cho chatbot ─────────────────────────────────────
COMPLIANT_CATEGORY = "100% template"   # mọi giá trị khác coi là CHƯA tuân thủ đầy đủ


def _load_rows():
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, "r", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def build_data_context() -> str:
    """Tóm tắt số liệu từ stories.csv để chatbot trả lời câu hỏi về dữ liệu."""
    from collections import Counter
    rows = _load_rows()
    if not rows:
        return "Hiện chưa có dữ liệu ticket nào được upload."

    total = len(rows)
    cat = Counter((r.get("Template Category") or "").strip() for r in rows)
    compliant = cat.get(COMPLIANT_CATEGORY, 0)
    noncompliant = total - compliant

    by_creator, by_squad = Counter(), Counter()
    for r in rows:
        if (r.get("Template Category") or "").strip() != COMPLIANT_CATEGORY:
            by_creator[(r.get("Người tạo") or "?").strip()] += 1
            by_squad[(r.get("Squad Name") or "?").strip()] += 1

    lines = [
        f"Tổng {total} ticket. Đạt '{COMPLIANT_CATEGORY}': {compliant}. "
        f"CHƯA tuân thủ đầy đủ: {noncompliant} ({round(noncompliant/total*100)}%).",
        "Phân bố Template Category: " + ", ".join(f"{k or '(trống)'}={v}" for k, v in cat.items()),
        "Người tạo có NHIỀU ticket chưa tuân thủ nhất: "
        + ", ".join(f"{n} ({c})" for n, c in by_creator.most_common(10)),
        "Squad có nhiều ticket chưa tuân thủ nhất: "
        + ", ".join(f"{n} ({c})" for n, c in by_squad.most_common(10)),
    ]
    return "\n".join(lines)


# ── AI chấm compliance ───────────────────────────────────────────
# Quy ước nhãn (giữ nguyên như cũ để dashboard không phải đổi):
#   đủ 3 mục -> 100% template | 2 mục -> 80% | 1 mục -> 50%
#   có nội dung nhưng 0 mục -> Không theo template | rỗng -> Trống
LABEL_BY_COUNT = {0: "Không theo template", 1: "50% template",
                  2: "80% template", 3: "100% template"}

CLASSIFY_PROMPT = """Bạn chấm Description của một user story theo Change Request Template gồm 3 mục bắt buộc:
1. "context"     — vì sao cần thay đổi (bối cảnh/vấn đề/mục tiêu).
2. "requirement" — mô tả thay đổi; chỉ cần ĐỦ 1 trong 3 loại (Product / Back-end & Front-end Technical / Configuration) là tính có.
3. "acceptance"  — Acceptance Criteria: điều kiện để coi là hoàn thành.

Đánh giá theo Ý NGHĨA, không cần đúng từ khoá. Với mỗi mục trả true nếu đã thể hiện rõ, false nếu thiếu/sơ sài.
CHỈ trả về JSON đúng dạng, KHÔNG giải thích:
{"context": true, "requirement": true, "acceptance": true}

DESCRIPTION:
"""


def _msg_text(resp) -> str:
    msg = resp.choices[0].message
    return msg.content or getattr(msg, "reasoning_content", "") or ""


def _parse_bool_json(text: str) -> dict:
    t = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    for m in reversed(re.findall(r"\{[^{}]*\}", t)):   # lấy JSON object cuối cùng
        try:
            return json.loads(m)
        except json.JSONDecodeError:
            continue
    return {}


def classify_description(desc: str) -> str:
    """Dùng AI (ANALYZE_MODEL) phân loại 1 Description thành nhãn template."""
    if not desc or not desc.strip():
        return "Trống"
    try:
        resp = llm.chat.completions.create(
            model=ANALYZE_MODEL,
            messages=[{"role": "user", "content": CLASSIFY_PROMPT + desc}],
            temperature=0,
            max_tokens=1500,
        )
        data = _parse_bool_json(_msg_text(resp))
    except Exception as e:
        print(f"[ANALYZE ERROR] {e}")
        data = {}

    if data:
        present = sum(1 for k in ("context", "requirement", "acceptance") if data.get(k))
    else:   # fallback nếu model trả rỗng/không parse được -> heuristic nhẹ
        low = desc.lower()
        present = min(3, sum(k in low for k in
                             ("context", "requirement", "acceptance", "bối cảnh", "tiêu chí")))
    return LABEL_BY_COUNT[present]


@app.route("/api/analyze", methods=["POST"])
def analyze():
    """AI chấm lại toàn bộ (hoặc 'limit' ticket) và ghi vào cột Template Category."""
    body = request.json or {}
    limit = body.get("limit")
    rows = _load_rows()
    if not rows:
        return jsonify({"error": "Chưa có dữ liệu. Hãy upload CSV trước."}), 404

    targets = rows[:int(limit)] if limit else rows

    def work(r):
        r["Template Category"] = classify_description(r.get("Description", ""))

    with ThreadPoolExecutor(max_workers=8) as ex:
        list(ex.map(work, targets))

    fieldnames = list(rows[0].keys())
    with open(DATA_FILE, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    from collections import Counter
    dist = dict(Counter((r.get("Template Category") or "").strip() for r in rows))
    return jsonify({"ok": True, "analyzed": len(targets), "total": len(rows),
                    "model": ANALYZE_MODEL, "distribution": dist})


def ticket_details_for(messages) -> str:
    """Nếu câu hỏi nhắc tới mã ticket (vd CR-1011), tra CSV và trả chi tiết ticket đó."""
    text = " ".join(m.get("content", "") for m in messages if m.get("role") == "user")
    ids = {x.upper() for x in re.findall(r"[A-Za-z]{2,6}-\d+", text)}
    if not ids:
        return ""
    found = [r for r in _load_rows() if (r.get("TicketID") or "").strip().upper() in ids]
    if not found:
        return ""
    blocks = []
    for r in found:
        desc = (r.get("Description") or "").strip() or "(trống)"
        blocks.append(
            f"[{(r.get('TicketID') or '').strip()}] "
            f"Người tạo: {r.get('Người tạo','')} | Squad: {r.get('Squad Name','')} | "
            f"Status: {r.get('Status','')} | Template Category: {r.get('Template Category','')}\n"
            f"Description: {desc}"
        )
    return ("CHI TIẾT TICKET NGƯỜI DÙNG ĐANG HỎI (đã có sẵn — hãy dùng để trả lời cụ thể, "
            "TUYỆT ĐỐI KHÔNG bảo người dùng tự dán lại mô tả):\n" + "\n\n".join(blocks))


# ── Chat ─────────────────────────────────────────────────────────
@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.json or {}
    messages = data.get("messages", [])
    if not messages:
        return jsonify({"error": "messages required"}), 400

    sys_msgs = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content":
            "DỮ LIỆU TICKET HIỆN TẠI (dùng để trả lời câu hỏi thống kê, ai/squad nào nhiều "
            "ticket chưa tuân thủ, tỉ lệ tuân thủ... KHÔNG bịa thêm):\n" + build_data_context()},
    ]
    ticket_ctx = ticket_details_for(messages)
    if ticket_ctx:
        sys_msgs.append({"role": "system", "content": ticket_ctx})
    full_messages = sys_msgs + messages

    try:
        response = llm.chat.completions.create(
            model=MODEL,
            messages=full_messages,
            temperature=0.6,
            max_tokens=1024,
        )
        reply = response.choices[0].message.content
        return jsonify({"reply": reply})
    except Exception as e:
        import traceback
        print(f"[CHAT ERROR] base_url={llm.base_url} model={MODEL}")
        print(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    print(f"🚀 Story Report Agent running at http://localhost:{port}")
    app.run(debug=False, host="0.0.0.0", port=port)
