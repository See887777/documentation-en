import os
import shutil
import re
from git import Repo
import frontmatter

# --- 配置区 ---
TIPS_REPO_URL = "https://github.com/tronprotocol/tips.git"
TMP_DIR = "./.tmp_tips_repo"
DEST_DIR = "docs/developers/tips"

def sync_and_build():
    if os.path.exists(TMP_DIR):
        shutil.rmtree(TMP_DIR)
    print(f"正在克隆仓库: {TIPS_REPO_URL}...")
    Repo.clone_from(TIPS_REPO_URL, TMP_DIR, depth=1)

    if os.path.exists(DEST_DIR):
        shutil.rmtree(DEST_DIR)
    os.makedirs(DEST_DIR)

    source_tips_path = os.path.join(TMP_DIR, "tips")
    if not os.path.exists(source_tips_path):
        for alt_name in ["TIPs", "Tips"]:
            if os.path.exists(os.path.join(TMP_DIR, alt_name)):
                source_tips_path = os.path.join(TMP_DIR, alt_name)
                break
        else:
            source_tips_path = TMP_DIR
            
    print(f"成功定位到 TIP 文件目录: {source_tips_path}")

    # 用一个扁平列表存储所有 TIP 的核心信息
    all_tips_data = []

    for filename in os.listdir(source_tips_path):
        if filename.endswith(".md") and filename.lower() != "readme.md":
            src_path = os.path.join(source_tips_path, filename)
            
            with open(src_path, 'r', encoding='utf-8') as f:
                content_str = f.read()
            
            post = frontmatter.loads(content_str)
            metadata = post.metadata
            content = post.content

            # 抢救早期不规范的 Markdown
            if not metadata:
                for line in content.split('\n')[:20]:
                    if ':' in line and not line.startswith('#'):
                        k, v = line.split(':', 1)
                        metadata[k.strip().lower()] = v.strip().replace('"', '').replace("'", "")

            # 提取元数据并清理空格
            status = str(metadata.get("status", "Unknown")).strip()
            tip_type = str(metadata.get("type", "Unknown")).strip()
            title = str(metadata.get("title", "Untitled")).strip()
            
            # 处理空类别
            if not tip_type or tip_type.lower() == "none":
                tip_type = "Unknown"
            
            tip_id_raw = metadata.get("tip", filename)
            nums = re.findall(r'\d+', str(tip_id_raw))
            tip_id = nums[0] if nums else str(tip_id_raw)

            # 重新组装规范的 Markdown
            new_post = frontmatter.Post(content, **metadata)
            new_post.metadata["tags"] = [status, tip_type]

            with open(os.path.join(DEST_DIR, filename), 'w', encoding='utf-8') as f:
                f.write(frontmatter.dumps(new_post))

            all_tips_data.append({
                "id": tip_id,
                "title": title,
                "author": str(metadata.get("author", "Unknown")).strip(),
                "status": status,
                "type": tip_type,
                "link": f"./{filename}"
            })

    # 将聚合好的数据交给生成器
    generate_category_pages(all_tips_data)
    print("TIP 页面及分类处理完成！")

def generate_category_pages(tips_data):
    """根据提取到的所有 Type 动态生成分类页面"""
    
    # 获取所有去重后的类别，并将 'All' 强制放在第一位
    all_types = set(item['type'] for item in tips_data)
    categories = ["All"] + sorted(list(all_types))
    print(f"--> 解析到的所有 TIP 类别 (Types): {categories}")

    # 为每个类别生成一个专属的 Markdown 文件
    for current_cat in categories:
        # 决定当前生成的文件名和过滤后的数据
        if current_cat == "All":
            filename = "index.md"
            filtered_tips = tips_data
        else:
            # 格式化类别名作为文件名，例如 'Standards Track' 变成 'category-standards-track.md'
            safe_cat_name = re.sub(r'[^a-zA-Z0-9]+', '-', current_cat.lower()).strip('-')
            filename = f"category-{safe_cat_name}.md"
            filtered_tips = [t for t in tips_data if t['type'] == current_cat]

        filepath = os.path.join(DEST_DIR, filename)

        # 将当前类别下的数据按 Status 分组
        status_dict = {}
        for item in filtered_tips:
            s = item['status']
            if s not in status_dict:
                status_dict[s] = []
            status_dict[s].append(item)

        preferred_order = ["Final", "Accepted", "Last Call", "Review", "Draft", "Stagnant", "Withdrawn", "Unknown"]
        actual_statuses = list(status_dict.keys())
        ordered_statuses = [s for s in preferred_order if s in actual_statuses] + sorted([s for s in actual_statuses if s not in preferred_order])

        # 开始写入 Markdown 文件
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("---\n")
            f.write("hide:\n  - toc\n")
            f.write("search:\n  boost: 2\n")
            f.write("---\n\n")
            f.write("# TRON Improvement Proposals (TIPs)\n\n")

            # --- 1. 渲染 Categories (跨页面跳转的分类栏) ---
            f.write("**Categories:**\n\n")
            cat_links = []
            for cat in categories:
                if cat == "All":
                    cat_filename = "index.md"
                else:
                    safe_name = re.sub(r'[^a-zA-Z0-9]+', '-', cat.lower()).strip('-')
                    cat_filename = f"category-{safe_name}.md"
                
                # 如果是当前页面所属的类别，使用 primary 颜色高亮它
                btn_class = "{: .md-button .md-button--primary }" if cat == current_cat else "{: .md-button }"
                cat_links.append(f"[{cat}](./{cat_filename}){btn_class}")

            f.write(" ".join(cat_links) + "\n\n")

            # --- 2. 渲染 Statuses (当前页面内的平滑锚点跳转) ---
            if ordered_statuses:
                f.write("**Quick Jump to Status:**\n\n")
                status_links = []
                for status in ordered_statuses:
                    anchor = status.lower().replace(" ", "-")
                    status_links.append(f"[{status}](#{anchor}){{: .md-button }}")
                f.write(" ".join(status_links) + "\n\n")

            f.write("---\n\n")

            # --- 3. 渲染具体的表格 ---
            for status in ordered_statuses:
                f.write(f"## {status}\n\n")
                f.write("| TIP | Title | Author | Type |\n")
                f.write("| :--- | :--- | :--- | :--- |\n")
                
                def sort_key(x):
                    nums = re.findall(r'\d+', str(x['id']))
                    return int(nums[0]) if nums else 999999
                        
                sorted_items = sorted(status_dict[status], key=sort_key)
                
                for item in sorted_items:
                    f.write(f"| {item['id']} | [{item['title']}]({item['link']}) | {item['author']} | {item['type']} |\n")
                f.write("\n")

if __name__ == "__main__":
    sync_and_build()