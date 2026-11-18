# Báo cáo Day 09 — Lê Ngọc Dũng, 2A202603103

## 1. Kết luận trước
**Hold**: đầu vào 224 ảnh, cửa vào loại 19 ảnh, xuất 205 ảnh dưới dạng bản nháp `clean_v1`. Sau duyệt mô phỏng 80/80 ảnh, không còn lỗi bắt buộc nhưng còn 38/205 ảnh có cảnh báo chưa duyệt (18,54% ≥ 10%). Nguồn: [tóm tắt](reports/08_summary.json), [manifest](export/clean_v1/manifest.json).

## 2. Lỗi và phân việc
Số liệu từ [danh sách lỗi v1](reports/02_error_list_v1.csv); mỗi mã đếm riêng, một ảnh có thể có nhiều lỗi. Mẫu số ảnh ở v1 là 224 ảnh raw; mục cấp dataset không có mẫu số ảnh. “Số mục báo” là số dòng CSV báo lỗi/cảnh báo, không phải số dòng nhãn được quét.

| Mã lỗi | Số mục báo / số ảnh | Phân việc |
|---|---:|---|
| BAD_CLASS_ID | 6 / 6 | Máy: bỏ dòng |
| BAD_CLASS_NAME | 2 / cấp dataset | Máy: chuẩn hóa tên |
| BAD_FORMAT | 3 / 3 | Máy: bỏ dòng |
| BAD_SIZE | 3 / 3 | Máy: loại ảnh |
| BOX_HUGE | 3 / 3 | Người: duyệt |
| BOX_OUT_OF_IMAGE | 8 / 8 | Máy: cắt khung |
| BOX_TINY | 6 / 4 | Người: duyệt |
| BOX_ZERO | 4 / 4 | Máy: bỏ dòng |
| CLASS_RARE | 4 / cấp dataset | Người: xem phân bố lớp |
| CORRUPT_IMAGE | 2 / 2 | Máy: loại ảnh |
| DUP_BOX | 7 / 7 | Máy: bỏ dòng |
| DUP_IMAGE_EXACT | 8 / 8 | Máy: loại ảnh |
| DUP_IMAGE_NEAR | 2 / 2 | Máy: loại ảnh |
| EMPTY_LABEL | 12 / 12 | Người: kiểm ảnh nền/thiếu nhãn |
| LEAK_TEST | 4 / 4 | Máy: loại ảnh |
| MISSING_LABEL_FILE | 6 / 6 | Người: gán nhãn |
| POSSIBLE_FALSE_POS | 29 / 27 | Người: kiểm nhãn thừa |
| POSSIBLE_LOOSE_BOX | 28 / 24 | Người: kiểm khung |
| POSSIBLE_MISSING | 53 / 52 | Người: kiểm thiếu nhãn |
| POSSIBLE_WRONG_CLASS | 18 / 18 | Người: kiểm lớp |

Cửa vào loại 2 ảnh hỏng, 3 quá nhỏ, 8 trùng byte, 2 gần trùng, 4 rò rỉ test/val. Autofix ghi 20 lần bỏ dòng, 8 lần cắt khung, 1 lần chuẩn hóa tên và 6 lần chuyển người gán; chỉ sửa bản sao.

Hàng đợi có 125 ảnh, xếp theo tổng trọng số lỗi và điểm tin cậy. Đầu hàng là `img_0020` (11,524 điểm, nhiều dấu hiệu), tiếp theo có ảnh thiếu nhãn như `img_0031`, `img_0053` (10 điểm). Trong 80 ảnh được duyệt mô phỏng, 74 ảnh mang 94/123 cảnh báo ngữ nghĩa ở v2; đây là cảnh báo được đưa qua người duyệt, không phải 94 lỗi thật đã xác nhận. Nguồn: [hàng đợi](reports/05_review_queue.csv), [nhật ký duyệt](reports/06_review_log.csv), [lỗi v2](reports/04_error_list_v2.csv).

## 3. Calibration (2 ngưỡng)
Nguồn: [bảng sweep tự sinh](calibration/calibration_report.md).

| Tham số | Khởi đầu → chọn | Precision / Recall trước → sau | Lý do |
|---|---|---|---|
| `duplicates.phash_dist` | 2 → 4 | Gần trùng: 1,00/0,50 → 1,00/0,67 | Bắt thêm ảnh gần trùng; 6–14 không tăng recall. Chọn mức nhỏ thận trọng vì loại nhầm sẽ mất ảnh tốt. |
| `second_opinion.conf` | 0,25 → 0,6 | Sai lớp: 0,56/0,83 → 0,62/0,83; thiếu: 0,50/1,00 → 0,57/1,00 | Giảm báo động giả ở hai nhóm, giữ recall thiếu nhãn. Đánh đổi: recall khung lỏng giảm 0,40 → 0,20. |

Điểm đánh lừa: calib chỉ 39 ảnh; mức phash 16 có precision 1,00 và recall 0,83 nhưng chưa chứng minh an toàn trên raw. Tôi mở hai cặp ở raw: `img_0042–img_0076` giống nhau; `img_0037–img_0143` cùng ảnh nhưng màu nhạt hơn. Hai cặp bị loại hợp lý, chưa đủ kết luận mọi cặp đều đúng. `POSSIBLE_FALSE_POS` giữ P/R 0,31/1,00 qua sweep vì dùng `fp_conf` riêng; tăng `conf` không khắc phục nhóm này.

## 4. Cửa chặn và điều pipeline không bắt được
Thí nghiệm `python -m pipeline.run --budget 0 --reports work/rep_nb --export-dir work/exp_nb` cho **Rework**, còn 6 lỗi bắt buộc, mã thoát **20**, `exported=null`; kiểm tra manifest trả **False**. Bản sao [summary thí nghiệm](evidence/gate_budget0_summary.json) được lưu nguyên nội dung. Đây là thí nghiệm riêng; kết quả chính vẫn Hold.

Hai hạn chế có bằng chứng: (1) ở ngưỡng đã chọn, recall khung lỏng chỉ 0,20, bỏ sót 4/5 ca chèn trên calib; (2) phash 4 chỉ bắt 4/6 ca gần trùng trên calib. Vì vậy kiểm thử xanh không chứng minh dữ liệu đã sạch. Qua xem 10 ảnh raw, tôi còn ghi nhận thiếu người (ảnh đầu và `img_0030`), nghi gán person vào máy ở `img_0002` và vật thể ở `img_0005`; các xe nhỏ/che khuất cần đối chiếu guideline trước khi tính lỗi.

## 5. Train: raw vs clean
**Chưa chạy**: ưu tiên hoàn thiện phần lõi trước khi thực hiện thí nghiệm Colab. Chưa có bằng chứng để kết luận clean giúp model tốt hơn raw.

## 6. Quyết định và ghi chú AI/Videcode
Giữ **Hold**, không tăng ngưỡng hoặc đổi ngân sách chỉ để đạt Release. Cần duyệt và xử lý tiếp cảnh báo tồn đọng, kiểm lại điểm mù; Release chỉ khi không còn lỗi bắt buộc và tỉ lệ ảnh cảnh báo chưa duyệt dưới 10%. CVAT và check thưởng: chưa làm. Repo GitHub public đã được xác minh; đang lưu commit và đẩy bài lên. Chưa nộp LMS.

- **Cách dùng AI/Videcode:** tôi cung cấp docstring và yêu cầu AI viết từng nhóm quy tắc cho 4 module, giải thích code, đọc lỗi và phân tích calibration. Sau đó ghép thành hàm đầy đủ; AI hỗ trợ tổng hợp báo cáo từ CSV/JSON.
- **Cách kiểm chứng:** tôi nhập/lưu code trong VS Code, chạy kiểm thử từng phần và toàn bộ (79 passed), xem khoảng 10 ảnh, kiểm hai cặp gần trùng và chạy thí nghiệm gate ngân sách 0. Duyệt 80 ảnh trong pipeline là mô phỏng có sẵn, không phải tôi sửa thủ công 80 ảnh.
- **Sai/thiếu và cách sửa:** hướng dẫn chèn code từng đoạn ban đầu chưa đủ rõ, gây chèn vào giữa `Issue(...)` hoặc thiếu `seen_boxes`; tôi đối chiếu traceback, nhờ AI làm rõ và sửa. AI ban đầu cũng hiểu nhầm người được tôi đánh dấu ở `img_0030`; tôi phóng to, chỉ rõ hai người bị che khuất để điều chỉnh nhận xét.

**Ghi chú kiểm tra trên Windows:** file `calibrate.py` còn nguyên hash bản đề, nhưng checker dùng đường dẫn `\` để đối chiếu danh sách bảo vệ dùng `/`, nên báo nhầm tham chiếu MANIFEST và data/calib trong file có sẵn. Giữ nguyên checker và file đề; kiểm tra bổ sung chỉ chuẩn hóa cách so đường dẫn trong bộ nhớ, không bỏ điều kiện kiểm tra.
