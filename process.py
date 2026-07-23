import sys
import os
import re
import base64
import requests
import json
import qrcode
from urllib.parse import unquote, quote

# گرفتن ورودی‌ها از اکشن
sub_type = sys.argv[1] if len(sys.argv) > 1 else 'Raw / Base64'
sub_urls = sys.argv[2] if len(sys.argv) > 2 else ''
custom_name = sys.argv[3] if len(sys.argv) > 3 else 'ArsenVPN'
repo_full = sys.argv[4] if len(sys.argv) > 4 else ''
# ورودی جدید برای چک کردن پرچم‌گذاری
enable_flags_str = sys.argv[5] if len(sys.argv) > 5 else 'true'
ENABLE_FLAGS = enable_flags_str.lower() in ['true', '1', 'yes']

def country_code_to_emoji(cc):
    if not cc or len(cc) != 2:
        return '🌐'
    return chr(ord(cc[0].upper()) + 127397) + chr(ord(cc[1].upper()) + 127397)

def get_flag(host):
    if not ENABLE_FLAGS:
        return ''
    try:
        # حذف پورت در صورت وجود
        clean_host = host.split(':')[0]
        res = requests.get(f'http://ip-api.com/json/{clean_host}?fields=countryCode', timeout=3)
        if res.status_code == 200:
            data = res.json()
            cc = data.get('countryCode', '')
            if cc:
                return country_code_to_emoji(cc) + ' '
    except Exception:
        pass
    return '🌐 '

def process_configs():
    urls = [u.strip() for u in re.split(r'[\r\n\s]+', sub_urls) if u.strip()]
    all_raw_configs = []

    for url in urls:
        try:
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                content = r.text.strip()
                # اگر بیس۶۴ بود دکود کن
                try:
                    decoded = base64.b64decode(content).decode('utf-8')
                    lines = decoded.splitlines()
                except Exception:
                    lines = content.splitlines()

                for line in lines:
                    line = line.strip()
                    if line and any(line.startswith(p) for p in ['vless://', 'vmess://', 'trojan://', 'ss://', 'ssr://']):
                        all_raw_configs.append(line)
        except Exception as e:
            print(f"Error fetching {url}: {e}")

    processed_configs = []
    for idx, config in enumerate(all_raw_configs, start=1):
        # استخراج هاست برای دریافت پرچم
        host = ""
        try:
            if config.startswith('vmess://'):
                b64_part = config.replace('vmess://', '')
                vdata = json.loads(base64.b64decode(b64_part).decode('utf-8'))
                host = vdata.get('add', '')
            else:
                host_part = config.split('@')[1] if '@' in config else config
                host = host_part.split(':')[0].split('/')[0].split('?')[0].split('#')[0]
        except Exception:
            host = ""

        flag = get_flag(host) if host else ('🌐 ' if ENABLE_FLAGS else '')
        new_remark = f"{flag}{custom_name} {idx:02d}".strip()

        # اعمال اسم جدید روی کانفیگ
        if config.startswith('vmess://'):
            try:
                b64_part = config.replace('vmess://', '')
                vdata = json.loads(base64.b64decode(b64_part).decode('utf-8'))
                vdata['ps'] = new_remark
                new_b64 = base64.b64encode(json.dumps(vdata).encode('utf-8')).decode('utf-8')
                processed_configs.append(f"vmess://{new_b64}")
            except Exception:
                processed_configs.append(config)
        elif '#' in config:
            base_part = config.split('#')[0]
            processed_configs.append(f"{base_part}#{quote(new_remark)}")
        else:
            processed_configs.append(f"{config}#{quote(new_remark)}")

    # ساخت فولدرها
    os.makedirs('sub-raw', exist_ok=True)
    os.makedirs('sub-clash', exist_ok=True)
    os.makedirs('sub-json', exist_ok=True)

    filename = f"{custom_name.lower().replace(' ', '_')}.txt"
    raw_path = os.path.join('sub-raw', filename)

    # ذخیره فایل RAW
    final_raw_content = "\n".join(processed_configs)
    with open(raw_path, 'w', encoding='utf-8') as f:
        f.write(final_raw_content)

    # ساخت QR Code
    qr_path = os.path.join('sub-raw', f"{custom_name.lower().replace(' ', '_')}_qr.png")
    if repo_full:
        raw_url = f"https://raw.githubusercontent.com/{repo_full}/main/{raw_path}"
        img = qrcode.make(raw_url)
        img.save(qr_path)

if __name__ == '__main__':
    process_configs()