import base64
import json
import os
import re
import urllib.parse
import urllib.request
import qrcode
import yaml

# ساخت پوشه‌های خروجی
for folder in ["sub-raw", "sub-clash", "sub-json"]:
    os.makedirs(folder, exist_ok=True)

def generate_qr(link, qr_filepath):
    try:
        qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=4)
        qr.add_data(link)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        img.save(qr_filepath)
    except Exception as e:
        print(f"⚠️ QR Error: {e}")

def safe_b64decode(s):
    if not s: return ""
    s = s.strip().replace("\r", "").replace("\n", "")
    missing_padding = len(s) % 4
    if missing_padding: s += '=' * (4 - missing_padding)
    try:
        return base64.b64decode(s).decode('utf-8', errors='ignore')
    except Exception:
        return s

def fetch_or_read(input_item):
    input_item = input_item.strip()
    if input_item.startswith(('http://', 'https://')):
        req = urllib.request.Request(input_item, headers={"User-Agent": "ClashMeta/1.16.0 v2rayNG/1.8.12"})
        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                content = response.read().decode("utf-8", errors="ignore")
                return content
        except Exception as e:
            print(f"⚠️ دانلود لینک با خطا مواجه شد ({input_item[:30]}...): {e}")
            return ""
    return input_item

def extract_proxies_from_clash_yaml(yaml_text):
    """استخراج پروکسی‌ها از فایل ساب Clash (YAML)"""
    try:
        data = yaml.safe_load(yaml_text)
        if isinstance(data, dict) and "proxies" in data and isinstance(data["proxies"], list):
            return data["proxies"]
    except Exception:
        pass
    return []

def extract_configs_from_text(text):
    """استخراج لینک‌های خام vless/vmess/trojan"""
    if not text: return []
    decoded = safe_b64decode(text)
    working_text = decoded if any(p in decoded for p in ["vless://", "vmess://", "trojan://", "ss://"]) else text
    pattern = r'(?:vless|vmess|trojan|ss|socks|hy2|tuic)://[^\s"]+'
    return re.findall(pattern, working_text)

def get_next_filename(folder_path, prefix="sub", extension=".txt"):
    count = 1
    while True:
        filename = f"{prefix}_{count}{extension}"
        if not os.path.exists(os.path.join(folder_path, filename)):
            return filename
        count += 1

def process_clash(inputs, custom_name, repo_info, clean_ip):
    all_proxies = []

    for item in inputs:
        content = fetch_or_read(item)
        if not content: continue

        # حالت اول: تست میده که آیا ورودی فایل YAML/Clash هست یا نه
        clash_proxies = extract_proxies_from_clash_yaml(content)
        if clash_proxies:
            print(f"✅ تعداد {len(clash_proxies)} پروکسی از فایل Clash استخراج شد.")
            all_proxies.extend(clash_proxies)
            continue

    if not all_proxies:
        print("❌ هیچ پروکسی معتبری داخل لینک‌های ورودی پیدا نشد!")
        return

    clean_proxies = []
    proxy_names = []
    
    # تغییر نام پروکسی‌ها و اعمال آی‌پی تمیز در صورت وجود
    for idx, proxy in enumerate(all_proxies, 1):
        if isinstance(proxy, dict):
            name = f"{custom_name} {idx:02d}"
            proxy['name'] = name
            if clean_ip and 'server' in proxy:
                proxy['server'] = clean_ip
            clean_proxies.append(proxy)
            proxy_names.append(name)

    clash_config = {
        'port': 7890,
        'socks-port': 7891,
        'allow-lan': True,
        'mode': 'rule',
        'log-level': 'info',
        'dns': {'enable': True, 'enhanced-mode': 'fake-ip', 'nameserver': ['https://1.1.1.1/dns-query', '8.8.8.8']},
        'proxies': clean_proxies,
        'proxy-groups': [
            {'name': custom_name, 'type': 'select', 'proxies': ['⚡ انتخاب خودکار'] + proxy_names},
            {'name': '⚡ انتخاب خودکار', 'type': 'url-test', 'proxies': proxy_names, 'url': 'http://www.gstatic.com/generate_204', 'interval': 300}
        ],
        'rules': ['GEOIP,LAN,DIRECT', f'MATCH,{custom_name}']
    }

    filepath = os.path.join("sub-clash", get_next_filename("sub-clash", "clash", ".yaml"))
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"# profile-title: {custom_name}\n\n" + yaml.dump(clash_config, allow_unicode=True, sort_keys=False))

    if repo_info: 
        generate_qr(f"https://raw.githubusercontent.com/{repo_info}/main/{filepath}", filepath.replace('.yaml', '_qr.png'))
    
    print(f"✅ ساب Clash با موفقیت ساخته شد: {filepath}")

def process_raw(inputs, custom_name, repo_info, clean_ip):
    all_configs = []
    for item in inputs:
        content = fetch_or_read(item)
        all_configs.extend(extract_configs_from_text(content))

    if not all_configs: return print("❌ هیچ کانفیگ معتبری یافت نشد!")

    new_lines = []
    for idx, line in enumerate(all_configs, 1):
        base_part = line.rsplit("#", 1)[0] if "#" in line else line
        new_lines.append(f"{base_part}#{urllib.parse.quote(f'{custom_name} {idx:02d}')}")

    filepath = os.path.join("sub-raw", get_next_filename("sub-raw", "sub", ".txt"))
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(base64.b64encode("\n".join(new_lines).encode("utf-8")).decode("utf-8"))

    if repo_info: generate_qr(f"https://raw.githubusercontent.com/{repo_info}/main/{filepath}", filepath.replace('.txt', '_qr.png'))
    print(f"✅ ساب RAW ساخته شد: {filepath}")

def process_json(inputs, custom_name, repo_info, clean_ip):
    all_proxies = []
    for item in inputs:
        content = fetch_or_read(item)
        clash_proxies = extract_proxies_from_clash_yaml(content)
        if clash_proxies:
            all_proxies.extend(clash_proxies)

    if not all_proxies: return print("❌ هیچ داده‌ای یافت نشد!")

    filepath = os.path.join("sub-json", get_next_filename("sub-json", "json", ".json"))
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump({"remarks": custom_name, "proxies": all_proxies}, f, ensure_ascii=False, indent=2)

    if repo_info: generate_qr(f"https://raw.githubusercontent.com/{repo_info}/main/{filepath}", filepath.replace('.json', '_qr.png'))
    print(f"✅ ساب JSON ساخته شد: {filepath}")

if __name__ == "__main__":
    sub_type = os.getenv("SUB_TYPE", "").strip()
    raw_urls = os.getenv("INPUT_URLS", "").strip()
    base_name = os.getenv("CUSTOM_NAME", "ArsenVPN").strip()
    repo_info = os.getenv("REPO_INFO", "").strip()
    clean_ip = os.getenv("CLEAN_IP", "").strip()

    inputs = [line.strip() for line in raw_urls.splitlines() if line.strip()]

    print(f"🔹 پردازش شروع شد - نوع: {sub_type} | تعداد ورودی‌ها: {len(inputs)}")

    st_lower = sub_type.lower()
    if "clash" in st_lower or st_lower == "2":
        process_clash(inputs, base_name, repo_info, clean_ip)
    elif "json" in st_lower or st_lower == "3":
        process_json(inputs, base_name, repo_info, clean_ip)
    else:
        process_raw(inputs, base_name, repo_info, clean_ip)