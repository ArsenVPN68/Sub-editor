import base64
import json
import os
import re
import sys
import urllib.parse
import urllib.request
import qrcode
import yaml

# ساخت پوشه‌ها
for folder in ["sub-raw", "sub-clash", "sub-json"]:
  os.makedirs(folder, exist_ok=True)


def generate_qr(link, qr_filepath):
  """تولید عکس QR Code برای لینک ساب"""
  try:
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(link)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    img.save(qr_filepath)
    print(f"🖼️ عکس QR Code ذخیره شد: {qr_filepath}")
  except Exception as e:
    print(f"⚠️ ارور در ساخت QR Code: {e}")


def fetch_content(url):
  """دریافت محتوای ساب با هدر کاربر واقعی"""
  req = urllib.request.Request(
      url,
      headers={
          "User-Agent": (
              "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
              " (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
          )
      },
  )
  try:
    with urllib.request.urlopen(req, timeout=15) as response:
      return response.read().decode("utf-8")
  except Exception as e:
    print(f"⚠️ خطا در دریافت {url}: {e}")
    return ""


def get_next_filename(folder_path, prefix="sub", extension=".txt"):
  """نام‌گذاری خودکار فایل جدید"""
  count = 1
  while True:
    filename = f"{prefix}_{count}{extension}"
    if not os.path.exists(os.path.join(folder_path, filename)):
      return filename
    count += 1


# ==========================================
# ۱. پردازش RAW (Base64 / URIs)
# ==========================================
def process_raw(urls, custom_name, repo_info):
  all_lines = []
  for url in urls:
    content = fetch_content(url).strip()
    if not content:
      continue

    try:
      decoded = base64.b64decode(content).decode("utf-8")
      lines = [line.strip() for line in decoded.splitlines() if line.strip()]
    except Exception:
      lines = [line.strip() for line in content.splitlines() if line.strip()]

    all_lines.extend(lines)

  new_lines = []
  index = 1

  for line in all_lines:
    if line.startswith(
        ("vless://", "vmess://", "trojan://", "ss://", "socks://")
    ):
      base_part = line.rsplit("#", 1)[0] if "#" in line else line
      new_title = urllib.parse.quote(f"{custom_name} {index:02d}")
      new_lines.append(f"{base_part}#{new_title}")
      index += 1

  if not new_lines:
    print("❌ هیچ کانفیگ معتبری یافت نشد!")
    return

  result_text = "\n".join(new_lines)
  encoded_result = base64.b64encode(result_text.encode("utf-8")).decode("utf-8")

  filename = get_next_filename("sub-raw", "sub", ".txt")
  filepath = os.path.join("sub-raw", filename)

  with open(filepath, "w", encoding="utf-8") as f:
    f.write(encoded_result)

  print(f"✅ ساب RAW جدید ساخته شد ({len(new_lines)} سرور): {filepath}")

  if repo_info:
    raw_url = f"https://raw.githubusercontent.com/{repo_info}/main/sub-raw/{filename}"
    qr_path = os.path.join("sub-raw", f"{os.path.splitext(filename)[0]}_qr.png")
    generate_qr(raw_url, qr_path)


# ==========================================
# ۲. پردازش CLASH (YAML بدون آسیب به ساختار)
# ==========================================
def process_clash(urls, custom_name, repo_info):
  all_proxies = []

  for url in urls:
    content = fetch_content(url)
    if not content:
      continue
    try:
      data = yaml.safe_load(content)
      if data and isinstance(data, dict) and "proxies" in data:
        all_proxies.extend(data["proxies"])
    except Exception as e:
      print(f"⚠️ ارور در خواندن کلش از {url}: {e}")

  if not all_proxies:
    print("❌ هیچ پروکسی کلش معتبری پیدا نشد!")
    return

  index = 1
  for proxy in all_proxies:
    if isinstance(proxy, dict) and "name" in proxy:
      proxy["name"] = f"{custom_name} {index:02d}"
      index += 1

  clash_config = {
      "port": 7890,
      "socks-port": 7891,
      "allow-lan": True,
      "mode": "rule",
      "log-level": "info",
      "profile": {"name": custom_name, "tracing": True},
      "proxies": all_proxies,
      "proxy-groups": [
          {
              "name": custom_name,
              "type": "select",
              "proxies": [p["name"] for p in all_proxies if "name" in p],
          }
      ],
  }

  filename = get_next_filename("sub-clash", "clash", ".yaml")
  filepath = os.path.join("sub-clash", filename)

  yaml_output = yaml.dump(
      clash_config,
      allow_unicode=True,
      sort_keys=False,
      default_flow_style=False,
  )
  header_comments = f"# profile-title: {custom_name}\n\n"

  with open(filepath, "w", encoding="utf-8") as f:
    f.write(header_comments + yaml_output)

  print(f"✅ ساب Clash جدید ساخته شد: {filepath}")

  if repo_info:
    raw_url = f"https://raw.githubusercontent.com/{repo_info}/main/sub-clash/{filename}"
    qr_path = os.path.join(
        "sub-clash", f"{os.path.splitext(filename)[0]}_qr.png"
    )
    generate_qr(raw_url, qr_path)


# ==========================================
# ۳. پردازش JSON (Sing-box)
# ==========================================
def process_json(urls, custom_name, repo_info):
  all_outbounds = []

  for url in urls:
    content = fetch_content(url)
    if not content:
      continue
    try:
      data = json.loads(content)
      outbounds = data.get("outbounds", []) if isinstance(data, dict) else data
      if isinstance(outbounds, list):
        all_outbounds.extend(outbounds)
    except Exception as e:
      print(f"⚠️ ارور در خواندن JSON از {url}: {e}")

  if not all_outbounds:
    print("❌ هیچ داده JSON معتبری پیدا نشد!")
    return

  index = 1
  for item in all_outbounds:
    if isinstance(item, dict) and "tag" in item:
      item["tag"] = f"{custom_name} {index:02d}"
      index += 1

  final_json = {"remarks": custom_name, "outbounds": all_outbounds}

  filename = get_next_filename("sub-json", "json", ".json")
  filepath = os.path.join("sub-json", filename)

  with open(filepath, "w", encoding="utf-8") as f:
    json.dump(final_json, f, ensure_ascii=False, indent=2)

  print(f"✅ ساب JSON جدید ساخته شد: {filepath}")

  if repo_info:
    raw_url = f"https://raw.githubusercontent.com/{repo_info}/main/sub-json/{filename}"
    qr_path = os.path.join(
        "sub-json", f"{os.path.splitext(filename)[0]}_qr.png"
    )
    generate_qr(raw_url, qr_path)


# ==========================================
# مدیریت اصلی ورودی‌ها
# ==========================================
if __name__ == "__main__":
  if len(sys.argv) > 3:
    sub_type = sys.argv[1].strip()
    urls_text = sys.argv[2].strip()
    base_name = sys.argv[3].strip()
    repo_info = sys.argv[4].strip() if len(sys.argv) > 4 else None

    # جداسازی لینک‌ها با خط بعد یا فاصله
    urls = [u.strip() for u in re.split(r"[\n\r\s]+", urls_text) if u.strip()]

    if "Raw" in sub_type or sub_type == "1":
      process_raw(urls, base_name, repo_info)
    elif "Clash" in sub_type or sub_type == "2":
      process_clash(urls, base_name, repo_info)
    elif "JSON" in sub_type or sub_type == "3":
      process_json(urls, base_name, repo_info)
    else:
      print("❌ نوع ساب نامعتبر است!")
  else:
    print("❌ ورودی‌های کافی ارسال نشده است.")