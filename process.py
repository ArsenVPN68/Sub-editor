import base64
import json
import urllib.request
import os

def decode_base64_safe(data_str):
    data_str = data_str.strip()
    missing_padding = len(data_str) % 4
    if missing_padding:
        data_str += '=' * (4 - missing_padding)
    try:
        return base64.b64decode(data_str).decode('utf-8', errors='ignore')
    except Exception:
        return data_str

def fetch_url_content(url):
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'v2rayNG/1.8.5'})
        with urllib.request.urlopen(req, timeout=10) as response:
            text = response.read().decode('utf-8', errors='ignore').strip()
            decoded = decode_base64_safe(text)
            return decoded
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return ""

def main():
    raw_input_b64 = os.environ.get("INPUT_DATA_B64", "")
    custom_name = os.environ.get("CUSTOM_NAME", "ArsenVPN")

    if not raw_input_b64:
        print("No input data provided.")
        return

    raw_input = decode_base64_safe(raw_input_b64)
    lines = [line.strip() for line in raw_input.splitlines() if line.strip()]

    raw_configs = []

    for line in lines:
        if line.startswith("http://") or line.startswith("https://"):
            sub_content = fetch_url_content(line)
            sub_lines = sub_content.splitlines()
            for s_line in sub_lines:
                s_line = s_line.strip()
                if any(s_line.startswith(proto) for proto in ["vless://", "vmess://", "trojan://", "ss://", "ssr://", "tuic://", "hy2://"]):
                    raw_configs.append(s_line)
        elif any(line.startswith(proto) for proto in ["vless://", "vmess://", "trojan://", "ss://", "ssr://", "tuic://", "hy2://"]):
            raw_configs.append(line)

    if not raw_configs:
        print("No configs found.")
        with open("sub.txt", "w", encoding="utf-8") as f:
            f.write("")
        return

    processed_configs = []
    for idx, config in enumerate(raw_configs, start=1):
        num_str = f"{idx:02d}"
        new_remark = f"{custom_name} {num_str}".strip()

        if config.startswith("vmess://"):
            try:
                b64_part = config.replace("vmess://", "")
                vdata = json.loads(decode_base64_safe(b64_part))
                vdata["ps"] = new_remark
                new_b64 = base64.b64encode(json.dumps(vdata).encode('utf-8')).decode('utf-8')
                processed_configs.append(f"vmess://{new_b64}")
            except Exception:
                processed_configs.append(config)
        elif "#" in config:
            base_part = config.split("#")[0]
            processed_configs.append(f"{base_part}#{urllib.parse.quote(new_remark)}")
        else:
            processed_configs.append(f"{config}#{urllib.parse.quote(new_remark)}")

    final_content = "\n".join(processed_configs)
    final_b64 = base64.b64encode(final_content.encode('utf-8')).decode('utf-8')

    with open("sub.txt", "w", encoding="utf-8") as f:
        f.write(final_b64)

    print(f"Successfully generated {len(processed_configs)} configs.")

if __name__ == "__main__":
    main()
