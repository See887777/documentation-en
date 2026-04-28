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

    # 安全清理模式：不删除整个文件夹，只清理自动生成的 tip 和 category 文件
    if not os.path.exists(DEST_DIR):
        os.makedirs(DEST_DIR)
    else:
        for f in os.listdir(DEST_DIR):
            if f.startswith("tip-") or f.startswith("category-") or f == "index.md":
                file_path = os.path.join(DEST_DIR, f)
                if os.path.isfile(file_path):
                    os.remove(file_path)

    source_tips_path = os.path.join(TMP_DIR, "tips")
    if not os.path.exists(source_tips_path):
        for alt_name in ["TIPs", "Tips"]:
            if os.path.exists(os.path.join(TMP_DIR, alt_name)):
                source_tips_path = os.path.join(TMP_DIR, alt_name)
                break
        else:
            source_tips_path = TMP_DIR
            
    print(f"成功定位到 TIP 文件目录: {source_tips_path}")

    all_tips_data = []
    ignored_files = {"readme.md", "license.md", "template.md"}

    for filename in os.listdir(source_tips_path):
        if filename.endswith(".md") and filename.lower() not in ignored_files:
            src_path = os.path.join(source_tips_path, filename)
            
            with open(src_path, 'r', encoding='utf-8') as f:
                content_str = f.read()
            
            post = frontmatter.loads(content_str)
            metadata = post.metadata
            content = post.content

            if not metadata:
                for line in content.split('\n')[:20]:
                    if ':' in line and not line.startswith('#'):
                        k, v = line.split(':', 1)
                        metadata[k.strip().lower()] = v.strip().replace('"', '').replace("'", "")

            status = str(metadata.get("status", "Unknown")).strip()
            title = str(metadata.get("title", "Untitled")).strip()
            
            # --- 核心修改：优先使用 Category，没有则回退到 Type ---
            raw_type = str(metadata.get("type", "")).strip()
            raw_category = str(metadata.get("category", "")).strip()
            
            if raw_category and raw_category.lower() != "none":
                tip_category = raw_category
            elif raw_type and raw_type.lower() != "none":
                tip_category = raw_type
            else:
                tip_category = "Unknown"
            
            tip_id_raw = metadata.get("tip", filename)
            nums = re.findall(r'\d+', str(tip_id_raw))
            tip_id = nums[0] if nums else str(tip_id_raw)

            new_post = frontmatter.Post(content, **metadata)
            # 给单篇文档注入 category 标签
            new_post.metadata["tags"] = [status, tip_category]

            with open(os.path.join(DEST_DIR, filename), 'w', encoding='utf-8') as f:
                f.write(frontmatter.dumps(new_post))

            all_tips_data.append({
                "id": tip_id,
                "title": title,
                "author": str(metadata.get("author", "Unknown")).strip(),
                "status": status,
                "category": tip_category, # 使用修正后的 category
                "link": f"./{filename}"
            })

    generate_category_pages(all_tips_data)
    print("TIP 页面及分类处理完成！")

def generate_category_pages(tips_data):
    # 根据提取到的 category 进行去重和排序
    all_categories = set(item['category'] for item in tips_data)
    categories = ["All"] + sorted(list(all_categories))
    print(f"--> 解析到的所有 TIP 分类 (Categories): {categories}")

    for current_cat in categories:
        if current_cat == "All":
            filename = "index.md"
            filtered_tips = tips_data
        else:
            safe_cat_name = re.sub(r'[^a-zA-Z0-9]+', '-', current_cat.lower()).strip('-')
            filename = f"category-{safe_cat_name}.md"
            filtered_tips = [t for t in tips_data if t['category'] == current_cat]

        filepath = os.path.join(DEST_DIR, filename)

        status_dict = {}
        for item in filtered_tips:
            s = item['status']
            if s not in status_dict:
                status_dict[s] = []
            status_dict[s].append(item)

        preferred_order = ["Final", "Accepted", "Last Call", "Review", "Draft", "Stagnant", "Withdrawn", "Unknown"]
        actual_statuses = list(status_dict.keys())
        ordered_statuses = [s for s in preferred_order if s in actual_statuses] + sorted([s for s in actual_statuses if s not in preferred_order])

        with open(filepath, "w", encoding="utf-8") as f:
            f.write("---\n")
            # 保持侧边栏显示，这里不加上 hide: toc
            f.write("search:\n  boost: 2\n")
            f.write("---\n\n")
            f.write("# TRON Improvement Proposals (TIPs)\n\n")

            # 1. 渲染 Categories
            f.write("**Categories:**\n\n")
            cat_links = []
            for cat in categories:
                if cat == "All":
                    cat_filename = "index.md"
                else:
                    safe_name = re.sub(r'[^a-zA-Z0-9]+', '-', cat.lower()).strip('-')
                    cat_filename = f"category-{safe_name}.md"
                
                btn_class = "{: .md-button .md-button--primary }" if cat == current_cat else "{: .md-button }"
                cat_links.append(f"[{cat}](./{cat_filename}){btn_class}")

            f.write(" ".join(cat_links) + "\n\n")

            # 2. 渲染 Statuses 锚点
            if ordered_statuses:
                f.write("**Quick Jump to Status:**\n\n")
                status_links = []
                for status in ordered_statuses:
                    anchor = status.lower().replace(" ", "-")
                    status_links.append(f"[{status}](#{anchor}){{: .md-button }}")
                f.write(" ".join(status_links) + "\n\n")

            f.write("---\n\n")

            # 3. 渲染具体的表格
            for status in ordered_statuses:
                f.write(f"## {status}\n\n")
                # 表头把 Type 改为 Category
                f.write("| TIP | Title | Author | Category |\n")
                f.write("| :--- | :--- | :--- | :--- |\n")
                
                def sort_key(x):
                    nums = re.findall(r'\d+', str(x['id']))
                    return int(nums[0]) if nums else 999999
                        
                sorted_items = sorted(status_dict[status], key=sort_key)
                
                for item in sorted_items:
                    # 表格内容输出 item['category']
                    f.write(f"| {item['id']} | [{item['title']}]({item['link']}) | {item['author']} | {item['category']} |\n")
                f.write("\n")

if __name__ == "__main__":
    sync_and_build()