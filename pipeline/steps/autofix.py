"""BƯỚC 2/4 — Sửa tự động những lỗi bắt buộc mà máy sửa được AN TOÀN.   ★★

Test:  pytest tests/test_autofix.py -q

`fix(ds, issues, cfg) -> list[dict]`: duyệt `issues` (chỉ lỗi severity ERROR), sửa thẳng vào thư mục `ds`,
và trả về danh sách thay đổi; mỗi phần tử có khoá: image, line, action, before, after
(đây chính là file `03_fixes.csv` — bằng chứng pipeline đã làm gì, người có thể kiểm lại).

| code lỗi                                       | cách sửa                                    | action           |
|------------------------------------------------|---------------------------------------------|------------------|
| BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO, DUP_BOX    | xoá dòng đó khỏi file nhãn                  | "drop_line"      |
| BOX_OUT_OF_IMAGE                               | cắt box về trong [0,1] (giữ nguyên lớp)     | "clip_box"       |
| MISSING_LABEL_FILE                             | KHÔNG sửa file (máy không thể bịa nhãn): ghi 1 dòng fix, before="(không có file)", after="chuyển người gán" | "needs_label" |
| BAD_CLASS_NAME                                 | ghi lại `names` trong data.yaml đúng `cfg["classes"]` | "rename_classes" |
| DUP_IMAGE_*, LEAK_TEST, CORRUPT_IMAGE, BAD_SIZE| xoá ảnh + nhãn khỏi `ds`                    | "remove_image"   |

Bẫy cần nghĩ tới (có test cho từng cái)
- Một file có NHIỀU dòng lỗi: số dòng trong `issues` là số dòng GỐC. Nếu xoá từng dòng một thì số dòng lệch.
  Gom theo file, rồi ghi lại MỘT lần.
- Sau khi cắt, box có thể không còn diện tích (nằm hẳn ngoài ảnh): lúc đó xoá dòng thay vì ghi box rỗng.
- Một dòng có 2 lỗi (vd. BOX_OUT_OF_IMAGE + DUP_BOX): xoá dòng thắng, chỉ ghi 1 fix `drop_line`, không ghi thêm `clip_box`. Dòng trống ở giữa file vẫn đếm vào số dòng gốc.
- Ảnh vừa bị xoá (DUP_IMAGE_*...) mà còn issue dòng của chính nó: bỏ qua êm, không được báo lỗi/chết.
- Không động tới lỗi WARN (cảnh báo là việc của người). Không sửa file ở `data/raw/` — chỉ sửa `ds`.
- Chạy lần 2 trên dữ liệu đã sửa phải không làm gì thêm (idempotent) — NGOẠI LỆ duy nhất: `needs_label` được ghi lại mỗi lần còn lỗi `MISSING_LABEL_FILE` (vì ảnh vẫn chưa có nhãn).

- `needs_label` KHÔNG tạo file nhãn rỗng (rỗng = "ảnh nền", khác với "chưa gán"). `review_queue` sẽ đẩy ảnh này lên đầu hàng đợi cho người.

Gợi ý: `yaml.safe_load / safe_dump`.
"""
from collections import defaultdict

import yaml

from ..common import ERROR, ROOT, parse_yolo_line


def fix(ds, issues, cfg):
        # Chặn sửa trực tiếp dữ liệu gốc.
    if ds.root.resolve() == (ROOT / "data" / "raw").resolve():
        raise ValueError("Chỉ sửa bản sao, không sửa data/raw")

    issues = list(issues)
    changes = []

    remove_codes = {
        "LEAK_TEST",
        "CORRUPT_IMAGE",
        "BAD_SIZE",
    }

    removed_images = {
        issue.image
        for issue in issues
        if issue.severity == ERROR
        and (
            issue.code in remove_codes
            or issue.code.startswith("DUP_IMAGE_")
        )
    }

    for stem in sorted(removed_images):
        image_path = ds.image_path(stem)
        label_path = ds.label_path(stem)
        removed_files = []

        if image_path is not None:
            removed_files.append(image_path.name)
            image_path.unlink()

        if label_path.exists():
            removed_files.append(label_path.name)
            label_path.unlink()

        if removed_files:
            changes.append(
                {
                    "image": stem,
                    "line": None,
                    "action": "remove_image",
                    "before": ", ".join(removed_files),
                    "after": "",
                }
            )
    drop_lines = defaultdict(set)
    clip_lines = defaultdict(set)

    drop_codes = {
        "BAD_FORMAT",
        "BAD_CLASS_ID",
        "BOX_ZERO",
        "DUP_BOX",
    }

    for issue in issues:
        if issue.severity != ERROR:
            continue

        if issue.image in removed_images:
            continue

        if issue.code == "BAD_CLASS_NAME":
            data = yaml.safe_load(
                ds.yaml_path.read_text(encoding="utf-8")
            ) or {}

            before = data.get("names")
            expected_names = list(cfg["classes"])

            if before != expected_names:
                data["names"] = expected_names

                ds.yaml_path.write_text(
                    yaml.safe_dump(data, allow_unicode=True),
                    encoding="utf-8",
                )

                changes.append(
                    {
                        "image": "data.yaml",
                        "line": issue.line,
                        "action": "rename_classes",
                        "before": str(before),
                        "after": str(expected_names),
                    }
                )

        elif issue.code == "MISSING_LABEL_FILE":
            if (
                ds.image_path(issue.image) is not None
                and not ds.label_path(issue.image).exists()
            ):
                changes.append(
                    {
                        "image": issue.image,
                        "line": issue.line,
                        "action": "needs_label",
                        "before": "(không có file)",
                        "after": "chuyển người gán",
                    }
                )

        elif issue.code in drop_codes and issue.line is not None:
            drop_lines[issue.image].add(issue.line)

        elif (
            issue.code == "BOX_OUT_OF_IMAGE"
            and issue.line is not None
        ):
            clip_lines[issue.image].add(issue.line)

    # Xử lý mọi file có dòng cần bỏ hoặc cần cắt khung.
    stems = sorted(set(drop_lines) | set(clip_lines))

    for stem in stems:
        label_path = ds.label_path(stem)
        if not label_path.exists():
            continue

        original_lines = label_path.read_text(
            encoding="utf-8"
        ).splitlines()

        kept_lines = []
        changed = False

        for line_no, text in enumerate(original_lines, start=1):
            action = None
            after = text

            # Bỏ dòng luôn được ưu tiên hơn cắt khung.
            if line_no in drop_lines[stem]:
                action = "drop_line"
                after = ""

            elif line_no in clip_lines[stem]:
                try:
                    class_id, cx, cy, w, h = parse_yolo_line(text)
                except (ValueError, OverflowError):
                    action = "drop_line"
                    after = ""
                else:
                    # Giới hạn từng cạnh trong khoảng 0–1.
                    left = max(0.0, min(1.0, cx - w / 2))
                    right = max(0.0, min(1.0, cx + w / 2))
                    top = max(0.0, min(1.0, cy - h / 2))
                    bottom = max(0.0, min(1.0, cy + h / 2))

                    new_w = right - left
                    new_h = bottom - top

                    if new_w <= 0 or new_h <= 0:
                        action = "drop_line"
                        after = ""
                    else:
                        new_cx = (left + right) / 2
                        new_cy = (top + bottom) / 2

                        after = (
                            f"{class_id} {new_cx:.10g} "
                            f"{new_cy:.10g} {new_w:.10g} "
                            f"{new_h:.10g}"
                        )
                        if after != text:
                            action = "clip_box"

            if action is not None:
                changes.append(
                    {
                        "image": stem,
                        "line": line_no,
                        "action": action,
                        "before": text,
                        "after": after,
                    }
                )
                changed = True

            if action != "drop_line":
                kept_lines.append(after)

        if changed:
            content = "\n".join(kept_lines)
            if kept_lines:
                content += "\n"
            label_path.write_text(content, encoding="utf-8")

    return changes