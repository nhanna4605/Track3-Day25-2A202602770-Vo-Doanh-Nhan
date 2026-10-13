# Lab 25B — Report

**Họ tên / nhóm:** Võ Doanh Nhân — MSV 2A202602770 (làm cá nhân)  **Commit:** ee794ca91e69dffc45b71c911e7f733c23d8dc61 (bản nộp; commit sau đó chỉ ghi hash này vào report)  **Điểm tự động (`make grade`):** 84 / 88 (4 điểm còn lại là dữ liệu SLO ẩn, chỉ giảng viên chấm được)

> Mọi số trong report lấy từ `reports/gameday/*.json`, `reports/cache/*.json`, `reports/workflows.json`,
> `reports/slo.json` và `reports/experiments.json` (sinh bằng `python scripts/report_experiments.py`, seed 25).
> Độ bền với băng ẩn được kiểm bằng `python scripts/stress_tapes.py` (mục 2 và mục 8).

## 1. Kết quả Game Day (naive vs của bạn)

Seed 25, băng public (`make compare`).

| Băng | Client | availability | p95 (s) | amplification | retry_ratio | cost/turn | recovery (s) | PASS? |
|---|---|---:|---:|---:|---:|---:|---:|:---:|
| G1 | naive | 0.7194 | 7.157 | 7.738 | 6.738 | 2.163 | 4.0 | FAIL |
| G1 | yours | 1.0 | 4.780 | 1.063 | 0.001 | 2.104 | 0.0 | PASS |
| G2 | naive | 0.456 | 15.034 | 9.904 | 8.904 | 4.627 | 155.0 | FAIL |
| G2 | yours | 1.0 | 6.441 | 1.019 | 0.003 | 2.078 | 0.0 | PASS |
| G3 | naive | 1.0 | 4.768 | 1.164 | 0.164 | 2.328 | 0.0 | FAIL |
| G3 | yours | 1.0 | 4.569 | 1.083 | 0.049 | 2.177 | 0.0 | PASS |
| G4 | naive | 1.0 | 13.764 | 1.004 | 0.004 | 2.008 | 0.0 | FAIL |
| G4 | yours | 1.0 | 5.626 | 1.014 | 0.002 | 2.072 | 0.0 | PASS |
| G5 | naive | 0.3699 | 5.359 | 17.03 | 16.03 | 2.124 | – | FAIL |
| G5 | yours | 0.8179 | 5.477 | 1.003 | 0.002 | 2.504 | – | PASS |
| G6 | naive | 0.517 | 4.836 | 12.344 | 11.344 | 2.009 | 0.0 | FAIL |
| G6 | yours | 1.0 | 5.961 | 1.055 | 0.018 | 2.196 | 0.0 | PASS |

Băng ẩn (lệch thời điểm, đổi cường độ): `scripts/stress_tapes.py` dịch mọi sự cố −60/−30/0/+30/+60 s, nhân cường độ
×0,8/×1/×1,25 (capacity, latency thêm, tỷ lệ lỗi, rate limit, traffic) và chạy 5 seed (25, 26, 27, 1, 2) = 75 lần/băng:
**cả 6 băng 75/75 PASS**. Biên xấu nhất: G1 amplification 1,087 (≤ 1,6); G2 availability 1,0, recovery 0 s; G3
retry_ratio 0,067 (≤ 0,10); G4 p95 5,86 s (≤ 10); G5 availability 0,8005 (≥ 0,78), 0 failover thừa; G6 availability
0,9996, 0 route không tương thích. Riêng tỷ lệ request hỏng của G5 không bị nhân lên: trên ~60% thì không client nào
đạt mức 78% (README §11), nên đó không phải cách kiểm hợp lệ.

## 2. Cấu hình client và lý do

Các sweep dưới đây đổi **một** tham số, giữ nguyên phần còn lại (`reports/experiments.json` → `sweeps`).

| Tham số | Giá trị | Vì sao (dựa trên băng nào, số liệu nào) |
|---|---:|---|
| attempt_timeout_s | 8 | G6: 30 s → availability 0,9488 FAIL (`deadline` 107 lượt: alpha-eu treo 30 s là hết deadline của user trước khi kịp fail over); 8 s → 1,0. 4 s → G4 có 1 lượt bỏ cuộc và cost/turn 2,124 so với 2,072 vì cắt cả request alpha chậm mà vẫn trả lời được. 8 s ≈ 2× p99 lúc bình thường của provider chậm nhất (beta: 1,8 s·e^(2,33·0,35) ≈ 4,1 s) và vẫn để đủ chỗ cho 2–3 lần fail over trong deadline 30 s. |
| max_attempts_per_provider | 2 | 1 retry cùng provider rồi fail over. G3 retry_ratio 0,049 (≤ 0,10); 4 không cải thiện gì (G2 p95 6,70 s so với 6,44 s). Thử 1 trên bộ stress: availability G6 tụt còn 0,9979 và G5 xuất hiện 2 failover thừa (với 2 là 0), nên giữ 2. |
| backoff_base_s / cap_s | 0,25 / 4 | Full jitter: lần retry đầu rơi trong U(0; 0,25 s) nên lỗi thoáng qua gần như không làm chậm (G3 p95 4,57 s); base 2 s → G2 p95 6,72 s, G3 4,95 s. Cap 4 s giữ mọi retry trong deadline 30 s. Có `retry_after` thì chờ đúng `retry_after` + U(0; base): G1 0 vi phạm. |
| retry_budget_ratio | 0,1 | Retry ≤ ~10% request đầu (+0,5 token/s, tối đa 20). Khi breaker đúng, budget hầu như không bị chạm (G3 retry_ratio 0,026 / 0,049 / 0,035 với ratio 0,02 / 0,1 / 1,0 — chênh lệch do tương tác với breaker, không đơn điệu). Vai trò thật là lưới an toàn khi breaker hỏng: thí nghiệm 1 (mục 3). |
| breaker.window_size / min_calls | 20 / 10 | min_calls 40 → breaker phản ứng muộn: G2 p95 19,4 s, amplification 1,38; G6 amplification 2,08, availability 0,9933 (14 lượt hết deadline). min_calls 3 cho số gần như bằng 10 trên băng nhưng sẽ trip vì 2–3 lỗi lẻ lúc traffic thấp (README: "no tripping on 2 errors at 3am"). Cửa sổ 20 nghĩa là chỉ nhìn ~2–3 s traffic gần nhất của alpha (~8 call/s). |
| breaker.failure_rate_threshold | 0,5 | G3 (30% lỗi 500): 0,5 không trip, alpha vẫn phục vụ, retry_ratio 0,049 trong giới hạn nhờ budget; 0,9 → retry_ratio 0,068, amplification 1,136. 0,2 trip ngay ở brown-out (retry_ratio 0,007) nhưng cũng trip khi chỉ 4/20 kết quả lỗi, quá nhạy với nhiễu. G2 không đổi theo tham số này vì breaker G2 mở do call chậm/timeout. |
| breaker.slow_call_s | 4 | G4 (alpha chậm thêm 5 s, không lỗi): 12 s → breaker không thấy gì, p95 13,77 s FAIL; 5 s → G2 p95 10,36 s; 4 s → G2 p95 6,44 s, G4 5,63 s; bộ stress: p95 xấu nhất G4 giảm từ 7,50 s (5 s) xuống 5,86 s (4 s). 3 s cho G2 p95 4,95 s nhưng sát p99 bình thường của beta (~4,1 s) nên dễ trip nhầm khi beta gánh tải. |
| breaker.open_duration_s | 10 | 2 s → probe quá dày vào provider còn yếu: G2 p95 8,00 s, G4 7,30 s. 60 s → p95 tốt hơn (G2 4,87 s) nhưng giữ traffic xa primary đã hồi phục tới 1 phút (beta đắt hơn 1,4×) và có thể làm hỏng `primary_share_after_restore` trên băng có cửa sổ ngắn hơn. 10 s: recovery 0 s, primary share 1,0 ở G2/G4/G6. |
| breaker.half_open_max_probes | 2 | 20 probe → dồn tải vào alpha đang hồi phục: G2 p95 12,06 s, amplification 1,063. 1 → 4,96 s; 2 → 6,44 s. Chọn 2 cùng `half_open_successes: 2` để breaker đóng trong một vòng probe thay vì hai vòng (số với 1 probe tốt hơn ở seed này, nên đây là đánh đổi có chủ ý: đóng nhanh hơn so với ít tải thử hơn). |
| quota_cooldown_s / min_time_left_s | 300 / 1 | G5: hết quota là lỗi billing, không tự hết sau vài giây; cooldown 300 s tránh gửi lại vào alpha/alpha-eu (0 failover thừa, 0 retry lỗi 400). Không bắt đầu attempt nếu còn < 1 s tới deadline. |

Sơ đồ quyết định của `on_error`:

```
lỗi ──classify──┬─ CLIENT_ERROR (400/401/422) ─ breaker.release ─> GiveUp("client_error")     (không retry, không fail over)
                ├─ QUOTA_EXHAUSTED (429 quota) ─ breaker.release ─> cooldown 300 s ─> route() ─> provider kế tiếp
                ├─ RATE_LIMITED (429 + retry-after) ─ release ─> cooldown tới now+retry_after (dùng chung mọi call)
                │                                                 └─> route(): fail over ngay; nếu hết thang thì chờ
                │                                                     cooldown ngắn nhất ≤ 5 s nếu kịp deadline
                └─ OVERLOADED / SERVER_ERROR / TIMEOUT ─ breaker.on_failure
                        tries < max_attempts AND kịp deadline AND không đang cooldown AND budget còn token?
                          ├─ có  ─> Send(cùng provider, delay = full jitter)
                          └─ không ─> idx += 1 ─> route() (bỏ qua provider đang cooldown / breaker OPEN)
route(): thang = fallback_order lọc theo tool calling; hết thang ─> GiveUp("no_provider_available")
```

## 3. Ba thí nghiệm (mỗi cái 3–5 câu + số)

1. **Retry budget là lớp phòng thủ cuối.** Breaker hỏng (`min_calls: 1e9`) + `max_attempts_per_provider: 5`:
   giữ budget thì G3 retry_ratio 0,068 (PASS), G2 amplification 1,378, retry_ratio 0,058, recovery 0 s; tắt budget
   thì G3 retry_ratio 0,158 (FAIL > 0,10), G2 amplification 1,58 (sát trần 1,6), retry_ratio 0,378, recovery 24 s, 58
   lượt hết deadline. Khi breaker *đúng*, bật/tắt budget gần như không đổi (G2 giống hệt; G3 0,049 so với 0,035) vì
   breaker đã chặn retry trước khi budget cạn. Vẫn cần cả hai: breaker bảo vệ **một provider** khi nó hỏng, còn budget
   giới hạn **tổng** retry của client bất kể nguyên nhân (breaker cấu hình sai, lỗi rải đều nhiều provider, lỗi dưới
   ngưỡng trip). Budget là thứ giữ retry ≤ 10% traffic khi mọi lớp khác sai.
2. **`attempt_timeout_s: 30`.** G6: availability 1,0 → 0,9488 (FAIL), `give_up_reasons` = {deadline: 107,
   no_provider_available: 15}; p95 lại *giảm* 5,96 → 5,44 s vì p95 chỉ tính lượt thành công: lượt bị treo 30 s ở
   alpha-eu (outage `hang`) hết deadline và biến mất khỏi mẫu (survivorship bias). G4 gần như không đổi (availability
   1,0, p95 5,63 → 5,61 s) vì alpha chỉ chậm thêm 5 s, chưa bao giờ chạm 8 s hay 30 s, và breaker slow-call đã đẩy
   traffic đi. Timeout đúng phải nhỏ hơn deadline của user trừ đi thời gian cần cho ít nhất một lần fail over, và lớn
   hơn p99 lúc bình thường: ở đây 30 − 2×(fail over) > timeout > ~4 s, nên 8 s.
3. **Bỏ lọc tool calling khỏi `ladder()`.** G6: `incompatible_routes` 0 → 257, availability 1,0 → 0,8922 (FAIL), mọi
   lỗi là `incompatible_model_output`. Nói theo ngôn ngữ product: khi model chính sập, 257 yêu cầu hoàn tiền được
   chuyển sang model rẻ không biết gọi công cụ; hệ thống "trả lời" nhưng không tra đơn hàng, không hoàn tiền được,
   nên khách nhận câu trả lời vô dụng — tệ hơn một lời xin lỗi rõ ràng vì trông như đã xử lý.

## 4. Workflow hoàn tiền

`make workflows` (500 phiên có crash, seed 25) và hai biến thể trong `reports/experiments.json` → `workflow_variants`.

| Executor | completion | crashes | duplicate refunds | duplicate emails | lost refunds | overpaid | wasted LLM / crash |
|---|---:|---:|---:|---:|---:|---:|---:|
| naive | 1.0 | 81 | 128 | 81 | 0 | 1 496 700 | 1.123 |
| yours | 1.0 | 66 | 0 | 0 | 0 | 0 | 0.303 |
| chỉ idempotency key (không checkpoint) | 1.0 | 68 | 0 | 0 | 0 | 0 | 1.132 |
| chỉ checkpoint (key ngẫu nhiên mỗi lần) | 1.0 | 70 | 82 | 69 | 0 | 1 303 000 | 0.286 |

Cả `yours` cũng đạt trên seed 1, 2, 3, 26, 27 (0 trùng, 0 mất, wasted 0,24–0,34 / crash).

- **Chỉ idempotency key chưa đủ:** tiền không bị trả trùng (payment trả lại kết quả cũ theo key), nhưng worker mới chạy
  lại mọi bước từ đầu, nên LLM bị gọi lại: 1,132 call phí / crash, vượt trần 0,6.
- **Chỉ checkpoint chưa đủ:** crash xảy ra *sau* khi payment đã commit nhưng *trước* khi checkpoint được ghi; worker mới
  không thấy checkpoint, gọi payment lần nữa với key mới → 82 hoàn tiền trùng, trả thừa 1 303 000. Checkpoint chỉ che
  được bước đã ghi xong; khoảng hở giữa "tiền đã đi" và "đã ghi lại" chỉ idempotency key mới đóng được.
- **Ghi checkpoint *trước* khi gọi payment:** nếu worker chết sau khi ghi nhưng trước khi request tới payment, worker mới
  thấy "đã xong" và bỏ qua bước đó: khách **mất** tiền hoàn mà hệ thống tin là đã hoàn (lost refund), và các bước sau dùng
  một `refund_id` không tồn tại. Simulator này chỉ gây crash *sau* khi service đã commit nên không đo được ca này bằng
  số; đây là lập luận từ thứ tự thao tác, không phải kết quả chạy.

## 5. Alerting & error budget

`make slo` (`reports/slo.json`).

| Sự cố | Mong đợi | Naive alerter | Burn-rate alerter | Độ trễ phát hiện |
|---|---|---|---|---:|
| checkout_bug | page | page (1 phút) | page | 27 phút (hạn 35) |
| provider_outage | page | page (0 phút) | page | 4 phút (hạn 8) |
| deploy_blip | none | **page nhầm** | không page | – |
| slow_leak | ticket | **không phát hiện** | ticket | 1 337 phút (hạn 1 800) |
| degraded_evening | page | page (214 phút) | page | 291 phút (hạn 330) |
| night_spike | none | **page nhầm** | không page | – |
| small_bump | none | **page nhầm** | không page | – |

Naive: 7 page, 3 false page, bỏ sót slow_leak → FAIL. Burn-rate: 3 page đúng, 1 ticket, 0 false page → PASS. Thêm 6 bộ
dữ liệu sinh bằng `scripts/make_sli_data.py --seed 1/2/3/7/42/99`: đều PASS, 0 false page.

Error budget 30 ngày (SLO 99,5%): 25 901 755 request, cho phép 129 508,8 lỗi, thực tế 55 618 lỗi → **đã tiêu 42,95%,
còn 57,05%**, availability 99,7853%. **Không đóng băng release** (chỉ đóng băng khi budget còn ≤ 0).

`small_bump` (20 phút ở 12% lỗi) không nên đánh thức ai: burn rate trong lúc xảy ra là 0,12/0,005 = 24×, nhưng trung
bình cửa sổ 1 giờ chỉ 12%·20/60 = 4% = 8× (< 14,4) và cửa sổ 6 giờ 12%·20/360 ≈ 1,3× (< 6), nên không luật page nào kích hoạt. Nó
chỉ tiêu 24·20/43 200 ≈ 1,1% budget tháng và đã tự hết; gọi người dậy không thay đổi được gì, chỉ làm đội on-call
mất niềm tin vào page (alert fatigue). Việc đúng là xem lại trong giờ làm việc nếu nó lặp lại.

## 6. Postmortem — Băng G2 với client naive (blameless)

*Hình `reports/gameday/G2_overload_storm.png`; số từ `reports/gameday/naive_G2_overload_storm_timeseries.csv` (gộp
theo cửa sổ 10 s) và `reports/gameday/naive.json`.*

**Tóm tắt (3 câu):** Lúc t=120 s, deployment alpha mất 75% GPU trong 3 phút. Client v1 retry mọi lỗi qua 3 tầng chồng
nhau (tối đa 36 attempt/call, delay cố định 0,2 s, không breaker, không fallback), đẩy tải lên alpha từ ~8 lên đỉnh 254
attempt/s, khiến tỷ lệ call thành công về 0 từ t≈140 s. Alpha hồi phục lúc t=300 s nhưng hệ thống chỉ hồi phục lúc
t≈455 s (recovery 155 s), vì chính lượng retry giữ alpha quá tải (metastable failure).

**Ảnh hưởng:** 1 285/2 362 lượt user thất bại (availability 45,6%); không có call nào thành công trong ~310 s (t≈140 →
≈450), dài hơn 1,7 lần chính sự cố (180 s). 34 475 attempt cho 3 481 call (amplification 9,9). Tổng chi phí xấp xỉ bản resilient (4 983 so với 4 908 đơn vị)
nhưng chỉ phục vụ được 45,6% lượt, nên chi phí trên mỗi lượt thành công gấp 2,2 lần (4,627 so với 2,078). Giả sử cả tháng chỉ có sự cố này và traffic đều 4 lượt/s:
10 368 000 lượt/tháng, budget 0,5% = 51 840 lượt lỗi, sự cố tiêu 1 285 ≈ **2,5% error budget tháng** trong ~5 phút.

**Timeline** (giây ảo):

| t | Sự kiện | Bằng chứng (số) |
|---:|---|---|
| 100–120 | Bình thường | 7,2–9,1 attempt/s vào alpha, 100% call thành công |
| 120 | alpha mất 75% năng lực | Hàng đợi bắt đầu dài; 120–130 s vẫn 32/32 call thành công nhưng ít call kết thúc hơn |
| 130–140 | Retry bắt đầu nhân tải | 51,9 attempt/s (×6 bình thường), 19/19 call kết thúc vẫn thành công |
| 140–150 | Retry storm | 214 attempt/s (đỉnh 254 lúc t=144), 0/47 call thành công |
| 150–300 | Sập hoàn toàn | 110–169 attempt/s mỗi 10 s, gấp 6–8 lần rate limit 20 rps của alpha; 0 call thành công |
| 300 | alpha hồi phục hoàn toàn | Năng lực trở lại 100%, nhưng 0/18 call thành công trong 300–310 s |
| 300–360 | Vẫn chưa hồi phục | ~15 attempt/s (attempt chờ timeout 8 s), 0 call thành công |
| 360–420 | Đợt bão thứ hai | 70–130 attempt/s, 0 call thành công |
| 430–450 | Tải giảm dần | 12–14 attempt/s; 450–460 s: 45/70 call thành công (64%) |
| 455 | Hồi phục (≥ 95% trong 30 s) | 460–470 s: 115/123 (93%); 470 s trở đi 100% — recovery_s = 155 |

**Trigger vs root cause:** Trigger là alpha mất 75% GPU trong 3 phút (sự kiện bên ngoài, sẽ còn xảy ra). Root cause là
cách client phản ứng: retry 3 tầng chồng nhau (4×3×3 = 36 attempt/call) với delay cố định 0,2 s, không jitter, không
retry budget, không breaker, không tôn trọng `retry-after`, không fallback. Một provider đang yếu nhận thêm tải đúng lúc
nó yếu nhất, nên một sự cố một phần biến thành sập toàn phần.

Vì sao không tự hồi phục sau t=300 (vòng lặp tự duy trì; phần này suy ra từ cơ chế mô phỏng và số tổng hợp, CSV không
ghi mã lỗi theo từng giây): khi client timeout sau 8 s, server **vẫn xử lý** request đó. Lúc t=300 hàng đợi alpha đầy
request mà client đã bỏ, nên request mới phải chờ gần hoặc quá 10 s → hết 8 s timeout hoặc bị trả 529 → client retry
ngay sau 0,2 s → thêm request vào đúng hàng đợi đó. Tải retry (70–150 attempt/s) luôn lớn hơn năng lực thật (~15 req/s)
và rate limit 20 rps, nên phần lớn attempt bị trả 429 (26 298 lỗi `rate_limit_exceeded`, 3 194 `overloaded_error`, 2 737
`client_timeout` trong cả băng). Vòng lặp chỉ dừng khi các call cũ hết 36 attempt hoặc hết deadline 30 s và bỏ cuộc
(655 `retries_exhausted`, 585 `deadline`), tức khoảng t≈430–455.

**Điều gì giúp / điều gì làm tệ hơn:** Giúp: deadline 30 s của lượt user cuối cùng cũng chặn được vòng lặp; alpha có
rate limit nên phần lớn retry bị trả 429 nhanh thay vì chiếm GPU. Làm tệ hơn: delay cố định 0,2 s đồng bộ hóa các đợt
retry; bỏ qua `retry-after`; không fallback dù alpha-eu và beta vẫn khỏe (cùng băng, client resilient đẩy 1 150 attempt
sang alpha-eu và 337 sang beta và giữ availability 100%); timeout 8 s bị bỏ qua nhưng công việc phía server thì không.

**Action items** (cụ thể, có owner, đo được):

| # | Hành động | Loại (prevent / detect / mitigate) | Owner | Cách kiểm chứng |
|---|---|---|---|---|
| 1 | Bỏ retry ở gateway và SDK, chỉ retry một tầng ở app với full jitter, tôn trọng `retry-after`, retry budget 10% | prevent | Đội platform (on-call ShopAgent) | CI chạy G2 mỗi PR: amplification ≤ 1,2 và retry_ratio ≤ 0,05 (hiện 1,019 và 0,003) |
| 2 | Circuit breaker sliding-window (lỗi + call chậm ≥ 4 s) và fallback ladder alpha → alpha-eu → beta có lọc tool calling | mitigate | Đội agent runtime | CI G2: recovery_s ≤ 30 và primary_share_after_restore ≥ 0,8 (hiện 0 s và 1,0); G6: incompatible_routes = 0 |
| 3 | Alert trên amplification (attempt/logical call) > 2 trong 5 phút và trên burn-rate đa cửa sổ của availability | detect | SRE | Replay CSV G2 naive: alert phải bắn trước t=150 (attempt/s vào alpha đã gấp ~6 lần bình thường ở 130–140 s); 0 false page trên `data/sli_30d.csv` |
| 4 | Game Day hằng quý với 6 băng sự cố, chạy `scripts/stress_tapes.py` (lệch thời điểm, đổi cường độ, 5 seed) | prevent | Tech lead reliability | 6/6 băng 75/75 PASS trước mỗi release lớn |

**Blameless:** sự cố không do một người cấu hình sai: mỗi tầng retry đều hợp lý khi nhìn riêng (SDK, gateway, app đều
"retry cho chắc"), nhưng không ai sở hữu tổng số retry của cả hệ thống. Hành động sửa tập trung vào thiết kế (một tầng
retry có budget) và quy trình (Game Day trong CI), không vào cá nhân.

## 7. Một điểm yếu còn lại

**Chi phí và năng lực khi chỉ còn beta gánh tải.** Ở G5, sau khi họ model A hết quota, mọi call đi beta (1,4 đơn vị/call)
nên cost/turn tăng từ ~2,0 lên 2,504; nếu beta cũng bị hạ rate limit (như G6) và traffic tăng, client sẽ dồn vào beta tới
khi bị 429 rồi phụ thuộc vào cooldown ngắn. Retry budget cũng là một bucket chung cho mọi provider, nên một provider tệ có
thể tiêu hết token của provider khác. Cách sửa: (1) adaptive concurrency / token bucket phía client cho từng provider theo
rate limit đã quan sát, để spillover sang provider kế tiếp *trước* khi bị 429; (2) với call `chat` (không cần tool), cho
phép gamma-mini (0,2/call) đứng trước beta khi alpha/alpha-eu không dùng được và chất lượng chấp nhận được; (3) budget riêng
cho từng provider. Kiểm chứng bằng một băng mới "A hết quota + traffic ×2" với ngưỡng cost/turn.

## 8. Cache (Part G)

Số từ `reports/cache/*.json` (`make cache`, seed 25).

| Client | availability | faq_availability | cache_hit_ratio | stale_served | wrong_answers | outdated_answers | cost/turn | PASS? |
|---|---:|---:|---:|---:|---:|---:|---:|:---:|
| resilient (không cache) | 0.8373 | 0.8424 | 0.0 | 0 | 0 | 0 | 1.386 | FAIL |
| cached (của bạn) | 0.9124 | 0.9645 | 0.592 | 192 | 0 | 2 | 0.955 | PASS |
| cached, tham số starter (0,80 / 600 / 0) | 0.8469 | 0.8587 | 0.742 | 0 | 181 | 80 | 0.921 | FAIL |

| Tham số `cache:` | Giá trị | Vì sao (số liệu nào) |
|---|---:|---|
| similarity_threshold | 0.92 | Đo trên catalog FAQ: paraphrase cùng ý có cosine ≥ 0,936, hai ý khác nhau nhưng gần nhau (hoàn tiền: chính sách vs thời gian; phí ship nội thành vs tỉnh…) có cosine ≤ 0,892, kể cả khi đổi seed catalog (2510, 1–5). 0,92 nằm giữa hai khoảng. Trên C1: 0,80 → 182 `other_question`; 0,86 → 1 `other_question`; 0,90 và 0,92 → 0 câu sai, hit 0,592; 0,97 → hit 0,495 (FAIL < 0,5) và cost/turn 1,02. |
| ttl_s | 30 | Chỉ TTL giới hạn được câu trả lời lỗi thời khi tài liệu đổi không báo trước (phí ship t=480): 30 s → 2 outdated, hit 0,592; 60 s → 3 / 0,652; 300 s → 95 outdated (FAIL > 15). Trên bộ stress (dịch thời điểm, 5 seed): TTL 30 → outdated xấu nhất 13, hit xấu nhất 0,567, 75/75 PASS; TTL 40 → outdated 17, 72/75; TTL 20 → hit 0,515 (sát 0,5). 30 cân bằng hai giới hạn ngược chiều. |
| max_stale_s | 900 | Cửa sổ dùng câu trả lời cũ khi mọi provider sập (t=240–360). 0 → faq_availability 0,8529 (FAIL < 0,93); 60 → 0,918 (FAIL: entry lưu trước sự cố đã quá hạn giữa chừng); 900 → 0,9645, 192 câu stale. Stale chỉ được phục vụ khi provider đã bỏ cuộc, và vẫn bị xóa theo webhook/prompt version, nên cửa sổ dài không gây câu sai (0 `wrong_answers`). |
| max_entries | 500 | Catalog có 18 ý chung; 500 dư cho mọi paraphrase, LRU chỉ để chặn tăng trưởng vô hạn. |

Thí nghiệm:

1. **Ngưỡng.** 0,80: hit 0,587, 182 câu sai, cost/turn 1,033; 0,92: hit 0,592, 0 câu sai, cost 0,955; 0,97: hit 0,495,
   0 câu sai, cost 1,02. Ở 0,80 toàn bộ lỗi là `other_question`: các cặp "gần mà khác" có cosine ~0,83–0,89 bị coi là
   cùng câu, ví dụ "Bao lâu thì nhận được tiền hoàn?" nhận câu trả lời của "Chính sách hoàn tiền thế nào?", hoặc phí ship
   đi tỉnh nhận giá nội thành. Ngưỡng quá chặt (0,97) thì paraphrase hợp lệ (cosine 0,94–0,97) bị miss.
2. **TTL.** 30 / 60 / 300 s → outdated 2 / 3 / 95, hit 0,592 / 0,652 / 0,731. Webhook không giúp gì cho `outdated_answers`
   vì sự kiện t=480 (phí ship) không gửi webhook: cache không biết tài liệu đã đổi. Webhook chỉ xử lý thay đổi *được báo*
   (chính sách hoàn tiền t=150: 0 `ignored_invalidation`). Với thay đổi không báo, giới hạn duy nhất là tuổi của entry:
   sau t=480, câu trả lời cũ sống tối đa `ttl_s` giây.
3. **Stale-if-error.** `max_stale_s: 0` → faq_availability 0,9645 → 0,8529 và hit 0,592 → 0,481: trong 2 phút mọi provider
   sập, câu FAQ chung không còn câu trả lời nào để phục vụ.

Trả lời:

- **Vì sao không cache câu hỏi cá nhân, kể cả theo từng user?** Câu trả lời phụ thuộc dữ liệu của chính user (trạng thái
  đơn, tiền hoàn, điểm) đổi theo phút và không có webhook nào báo; trả câu cũ là nói sai về tiền của khách. Câu hỏi của
  hai user chỉ khác số đơn nên cosine ~0,99: một lỗi scope là lộ đơn hàng của người khác (`other_user`), rủi ro quyền
  riêng tư lớn hơn nhiều so với lợi ích. Cache theo từng user cũng gần như không có hit (mỗi user ít khi hỏi lại đúng câu
  trong vài phút), nên chỉ có rủi ro mà không tiết kiệm được gì.
- **Khi mọi provider sập mà dashboard vẫn xanh nhờ cache, alert dựa trên số nào?** Dựa trên sức khỏe phía provider chứ
  không phải tỷ lệ trả lời: (1) tỷ lệ call tới provider thành công / số `GiveUp` của client bên trong (ở C1, không cache thì
  availability tụt còn 0,8373); (2) `stale_served` theo phút (bình thường 0; trong sự cố 192 câu) và tỷ lệ phục vụ từ cache
  tăng đột biến; (3) availability của lượt không phải FAQ (cần tool call), vốn không được cache cứu. SLI nên tính câu trả
  lời stale là "degraded" thay vì "good", để error budget vẫn phản ánh sự cố.
