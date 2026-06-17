# User Story Compliance Agent

Agent dùng AI chấm mức độ tuân thủ **Change Request Template** của user story, tổng hợp
thành báo cáo trực quan, kèm một **trợ lý PM** hỏi đáp. Chạy trên **GreenNode AgentBase**,
lõi AI dùng **GreenNode MaaS** (`google/gemma-4-31b-it`).

## Vấn đề
User story / ticket thường viết thiếu so với Change Request Template (Context, Requirement,
Acceptance Criteria), khiến grooming mất thời gian hỏi lại, chất lượng yêu cầu thấp, và
**không đo lường được** tỉ lệ tuân thủ hay biết người/squad nào hay viết thiếu.

## Người dùng
Project Manager, Team Lead, BA/PO, QA và đội phát triển.

## Agent giải quyết thế nào
1. **AI chấm tự động:** với mỗi ticket, model `google/gemma-4-31b-it` (GreenNode MaaS) đọc
   Description, đánh giá *theo ngữ nghĩa* 3 mục bắt buộc — Context, Requirement (đủ 1 trong 3
   loại Product / BE&FE Technical / Configuration), Acceptance Criteria — rồi phân loại mức
   tuân thủ (100% / 80% / 50% / Không theo template / Trống).
2. **Báo cáo trực quan:** KPI tổng quan, biểu đồ phân bố & theo squad/tháng, bảng ticket kèm
   các mục còn thiếu, ô sửa Description tại chỗ.
3. **Trợ lý PM (chatbot):** giọng ân cần, có kỹ năng sư phạm — hướng dẫn cách viết từng mục,
   trả lời câu hỏi dữ liệu ("user/squad nào nhiều ticket chưa đạt nhất"), tra chi tiết ticket
   theo mã (vd `CR-1011`) và gợi ý hoàn thiện.

## Giá trị
Biến việc kiểm tra template từ thủ công thành **tự động đo được**, chỉ ra điểm yếu theo
người/squad, và hỗ trợ viết tốt hơn ngay từ đầu → giảm thời gian review, nâng chất lượng yêu
cầu. Toàn bộ chạy trên hạ tầng GreenNode (MaaS + AgentBase).

## Kiến trúc
- `server.py` — Flask service (cổng 8080): `/health`, `/api/data`, `/api/upload`,
  `/api/analyze` (AI chấm), `/api/update`, `/api/chat` (trợ lý PM).
- `index.html` — dashboard + trợ lý PM (panel mở/đóng).
- `data/stories.csv` — bộ dữ liệu mẫu (synthetic) để demo.
- `Dockerfile` — đóng gói container cổng 8080.

## Biến môi trường
| Biến | Mô tả |
| --- | --- |
| `LLM_BASE_URL` | `https://maas-llm-aiplatform-hcm.api.vngcloud.vn/v1` |
| `LLM_API_KEY` | API key GreenNode MaaS (ACTIVE) |
| `LLM_MODEL` | model cho chatbot (vd `google/gemma-4-31b-it`) |
| `ANALYZE_MODEL` | model cho AI chấm (mặc định `google/gemma-4-31b-it`) |

> ⚠️ Không commit API key vào repo. Đặt biến qua Environment Variables của Agent Runtime.

## Chạy local
```bash
cp runtime.env.example runtime.env   # điền LLM_API_KEY thật (KHÔNG commit file này)
docker build --platform linux/amd64 -t user-story-report-agent-gemma:1.3 .
docker run --platform linux/amd64 --rm -p 8080:8080 --env-file runtime.env user-story-report-agent-gemma:1.3
# mở http://localhost:8080 -> "Phân tích bằng AI"
```

## Deploy lên GreenNode AgentBase
Push image lên Container Registry rồi tạo/Update Agent Runtime với Image URL
`vcr.vngcloud.vn/111480-abp112158/user-story-report-agent-gemma:1.3`, cổng 8080, set các biến môi trường ở trên.

---
*Lưu ý: agent có sử dụng AI; kết quả mang tính hỗ trợ, người dùng nên rà soát lại.*
*Dữ liệu trong repo là dữ liệu mẫu/synthetic, không chứa thông tin thật.*
