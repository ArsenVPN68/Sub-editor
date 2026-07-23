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
        req = urllib.request.Request(input_item, headers={"User-Agent": "v2rayNG/1.8.12"})
        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                return response.read().decode("utf-8", errors="ignore")
        except Exception as e:
            print(f"⚠️ Fetch Error: {e}")
            return ""
    return input_item

def clash_dict_to_vless_uri(p):
    """تبدیل دیکشنری پروکسی کلاش به لینک vless://"""
    try:
        if p.get('type') != 'vless': return None
        uuid = p.get('uuid')
        server = p.get('server')
        port = p.get('port')
        name = p.get('name', 'VLESS')
        
        ws_opts = p.get('ws-opts', {})
        path = ws_opts.get('path', '/')
        headers = ws_opts.get('headers', {})
        host = headers.get('Host', '')
        
        query = {
            'type': p.get('network', 'ws'),
            'security': 'tls' if p.get('tls') else 'none',
            'path': path
        }
        if host: query['host'] = host
        if p.get('servername'): query['sni'] = p.get('servername')
        if p.get('fp'): query['fp'] = p.get('fp')

        q_str = urllib.parse.urlencode(query)
        return f"vless://{uuid}@{server}:{port}?{q_str}#{urllib.parse.quote(name)}"
    except Exception:
        return None

def extract_configs_from_text(text):
    if not text: return []
    
    # 1. برسی اینکه آیا ورودی یک فایل JSON با آرایه proxies است یا خیر
    try:
        data = json.loads(text)
        if isinstance(data, dict) and "proxies" in data:
            extracted = []
            for p in data["proxies"]:
                uri = clash_dict_to_vless_uri(p)
                if uri: extracted.append(uri)
            if extracted: return extracted
    except Exception:
        pass

    # 2. بررسی رمزنگاری Base64 یا متن معمولی
    decoded = safe_b64decode(text)
    working_text = decoded if any(p in decoded for p in ["vless://", "vmess://", "trojan://", "ss://"]) else text
    
    pattern = r'(?:vless|vmess|trojan|ss|socks|hy2|tuic)://[^\s"#]+(?:#[^\s"]*)?'
    found = re.findall(pattern, working_text)
    
    if not found:
        lines = [line.strip() for line in working_text.splitlines() if line.strip()]
        for line in lines:
            if any(line.startswith(p) for p in ["vless://", "vmess://", "trojan://", "ss://", "socks://", "hy2://", "tuic://"]):
                found.append(line)
    return found

def remove_duplicates(configs):
    seen = set()
    unique = []
    for cfg in configs:
        base = cfg.rsplit("#", 1)[0] if "#" in cfg else cfg
        if base not in seen:
            seen.add(base)
            unique.append(cfg)
    return unique

def get_next_filename(folder_path, prefix="sub", extension=".txt"):
    count = 1
    while True:
        filename = f"{prefix}_{count}{extension}"
        if not os.path.exists(os.path.join(folder_path, filename)):
            return filename
        count += 1

def parse_uri_to_clash(link):
    try:
        link = link.strip()
        if not link: return None

        if link.startswith('vless://'):
            parsed = urllib.parse.urlparse(link)
            user_info = parsed.netloc.split('@')
            uuid = user_info[0]
            host_port = user_info[1].split(':')
            params = urllib.parse.parse_qs(parsed.query)
            remark = urllib.parse.unquote(parsed.fragment) or "VLESS"
            security = params.get('security', [''])[0]
            net_type = params.get('type', [''])[0]

            proxy = {
                'name': remark, 'type': 'vless', 'server': host_port[0], 
                'port': int(host_port[1]), 'uuid': uuid, 'udp': True, 
                'tls': security in ['tls', 'reality'], 'skip-cert-verify': True
            }
            if security == 'reality':
                proxy['reality-opts'] = {'public-key': params.get('pbk', [''])[0]}
                if 'sid' in params: proxy['reality-opts']['short-id'] = params['sid'][0]
            if 'sni' in params: proxy['servername'] = params['sni'][0]
            if net_type == 'ws':
                proxy['network'] = 'ws'
                proxy['ws-opts'] = {'path': params.get('path', ['/'])[0]}
                if 'host' in params: proxy['ws-opts']['headers'] = {'Host': params['host'][0]}
            elif net_type == 'grpc':
                proxy['network'] = 'grpc'
                proxy['grpc-opts'] = {'grpc-service-name': params.get('serviceName', params.get('path', ['']))[0]}
            return proxy

        elif link.startswith('vmess://'):
            b64_part = link.replace('vmess://', '')
            data = json.loads(safe_b64decode(b64_part))
            proxy = {'name': data.get('ps', 'VMess'), 'type': 'vmess', 'server': data.get('add'), 'port': int(data.get('port', 443)), 'uuid': data.get('id'), 'alterId': int(data.get('aid', 0)), 'cipher': 'auto', 'udp': True, 'tls': data.get('tls') == 'tls', 'skip-cert-verify': True}
            net = data.get('net')
            if net == 'ws':
                proxy['network'] = 'ws'
                proxy['ws-opts'] = {'path': data.get('path', '/')}
                if data.get('host'): proxy['ws-opts']['headers'] = {'Host': data.get('host')}
            elif net == 'grpc':
                proxy['network'] = 'grpc'
                proxy['grpc-opts'] = {'grpc-service-name': data.get('path', '')}
            if data.get('sni'): proxy['servername'] = data.get('sni')
            return proxy
    except Exception: pass
    return None

def process_raw(inputs, custom_name, repo_info):
    all_configs = []
    for item in inputs:
        content = fetch_or_read(item)
        all_configs.extend(extract_configs_from_text(content))

    all_configs = remove_duplicates(all_configs)
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

def process_clash(inputs, custom_name, repo_info):
    all_proxies = []
    for item in inputs:
        content = fetch_or_read(item)
        try:
            data = json.loads(content)
            if isinstance(data, dict) and "proxies" in data:
                all_proxies.extend(data["proxies"])
                continue
        except Exception: pass

        for link in remove_duplicates(extract_configs_from_text(content)):
            proxy = parse_uri_to_clash(link)
            if proxy: all_proxies.append(proxy)

    if not all_proxies: return print("❌ هیچ پروکسی معتبری پیدا نشد!")

    proxy_names = []
    clean_proxies = []
    for idx, proxy in enumerate(all_proxies, 1):
        if isinstance(proxy, dict):
            name = f"{custom_name} {idx:02d}"
            proxy['name'] = name
            proxy_names.append(name)
            clean_proxies.append(proxy)

    clash_config = {
        'port': 7890, 'socks-port': 7891, 'allow-lan': True, 'mode': 'rule', 'log-level': 'info',
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

    if repo_info: generate_qr(f"https://raw.githubusercontent.com/{repo_info}/main/{filepath}", filepath.replace('.yaml', '_qr.png'))
    print(f"✅ ساب Clash ساخته شد: {filepath}")

def process_json(inputs, custom_name, repo_info):
    all_outbounds = []
    for item in inputs:
        content = fetch_or_read(item)
        try:
            data = json.loads(content)
            outbounds = data.get("proxies", data.get("outbounds", []))
            if isinstance(outbounds, list): all_outbounds.extend(outbounds)
        except Exception: pass

    if not all_outbounds: return print("❌ هیچ داده JSON معتبری پیدا نشد!")

    for idx, item in enumerate(all_outbounds, 1):
        if isinstance(item, dict) and "name" in item: item["name"] = f"{custom_name} {idx:02d}"
        elif isinstance(item, dict) and "tag" in item: item["tag"] = f"{custom_name} {idx:02d}"

    filepath = os.path.join("sub-json", get_next_filename("sub-json", "json", ".json"))
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump({"remarks": custom_name, "proxies": all_outbounds}, f, ensure_ascii=False, indent=2)

    if repo_info: generate_qr(f"https://raw.githubusercontent.com/{repo_info}/main/{filepath}", filepath.replace('.json', '_qr.png'))
    print(f"✅ ساب JSON ساخته شد: {filepath}")

if __name__ == "__main__":
    sub_type = os.getenv("SUB_TYPE", "").strip()
    raw_urls = os.getenv("INPUT_URLS", "").strip()
    base_name = os.getenv("CUSTOM_NAME", "ArsenVPN").strip()
    repo_info = os.getenv("REPO_INFO", "").strip()

    inputs = [line.strip() for line in raw_urls.splitlines() if line.strip()]

    print(f"🔹 دریافت شد - نوع: {sub_type} | تعداد ورودی‌ها: {len(inputs)}")

    if "Raw" in sub_type or sub_type == "1":
        process_raw(inputs, base_name, repo_info)
    elif "Clash" in sub_type or sub_type == "2":
        process_clash(inputs, base_name, repo_info)
    elif "JSON" in sub_type or sub_type == "3":
        process_json(inputs, base_name, repo_info)
    else:
        print("❌ نوع ساب‌اسکریپشن نامعتبر است.")