import os
import shutil
import re
from git import Repo
import frontmatter

# --- Configuration ---
TIPS_REPO_URL = "https://github.com/tronprotocol/tips.git"
TMP_DIR = "./.tmp_tips_repo"
DEST_DIR = "docs/developers/tips"

def sync_and_build():
    if os.path.exists(TMP_DIR):
        shutil.rmtree(TMP_DIR)
    print(f"Cloning repository: {TIPS_REPO_URL}...")
    Repo.clone_from(TIPS_REPO_URL, TMP_DIR, depth=1)

    # Safe cleanup mode: do not delete the entire directory, only clean up auto-generated files
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
            
    print(f"Successfully located TIPs directory: {source_tips_path}")

    all_tips_data = []
    # Define a list of files to ignore (use lowercase to prevent case sensitivity issues)
    ignored_files = {"readme.md", "license.md", "template.md"}

    for filename in os.listdir(source_tips_path):
        if filename.endswith(".md") and filename.lower() not in ignored_files:
            src_path = os.path.join(source_tips_path, filename)
            
            with open(src_path, 'r', encoding='utf-8') as f:
                content_str = f.read()
            
            post = frontmatter.loads(content_str)
            metadata = post.metadata
            content = post.content

            # Rescue early non-standard Markdown files without proper YAML frontmatter
            if not metadata:
                for line in content.split('\n')[:20]:
                    if ':' in line and not line.startswith('#'):
                        k, v = line.split(':', 1)
                        metadata[k.strip().lower()] = v.strip().replace('"', '').replace("'", "")

            status = str(metadata.get("status", "Unknown")).strip()
            title = str(metadata.get("title", "Untitled")).strip()
            
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
            new_post.metadata["tags"] = [status, tip_category]

            with open(os.path.join(DEST_DIR, filename), 'w', encoding='utf-8') as f:
                f.write(frontmatter.dumps(new_post))

            all_tips_data.append({
                "id": tip_id,
                "title": title,
                "author": str(metadata.get("author", "Unknown")).strip(),
                "status": status,
                "category": tip_category,
                "link": f"./{filename}"
            })

    generate_category_pages(all_tips_data)
    print("TIP pages and categories processing completed!")

def generate_category_pages(tips_data):
    # ==========================================
    # 1. Custom Category Order
    # ==========================================
    preferred_category_order = ["Core", "Networking", "Interface", "TRC", "VM", "Informational"]
    all_categories = set(item['category'] for item in tips_data)
    
    categories = ["All"]
    for pref_cat in preferred_category_order:
        # Case-insensitive matching for robustness
        matched_cat = next((c for c in all_categories if c.lower() == pref_cat.lower()), None)
        if matched_cat:
            categories.append(matched_cat)
            all_categories.remove(matched_cat)
    
    # Append other categories not in the preset list alphabetically at the end
    categories.extend(sorted(list(all_categories)))
    print(f"--> Sorted TIP Categories: {categories}")

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

        # ==========================================
        # 2. Custom Status Order
        # ==========================================
        preferred_status_order = ["Draft", "Last Call", "Accepted", "Final", "Deferred"]
        actual_statuses = list(status_dict.keys())
        ordered_statuses = []
        
        for pref_status in preferred_status_order:
            matched_status = next((s for s in actual_statuses if s.lower() == pref_status.lower()), None)
            if matched_status:
                ordered_statuses.append(matched_status)
                actual_statuses.remove(matched_status)
        
        # Append other statuses not in the preset list alphabetically at the end
        ordered_statuses.extend(sorted(actual_statuses))

        with open(filepath, "w", encoding="utf-8") as f:
            f.write("---\n")
            f.write("search:\n  boost: 2\n")
            f.write("---\n\n")
            f.write("# TRON Improvement Proposals (TIPs)\n\n")

            # Render Categories
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

            # Render Status anchors
            if ordered_statuses:
                f.write("**Quick Jump to Status:**\n\n")
                status_links = []
                for status in ordered_statuses:
                    anchor = status.lower().replace(" ", "-")
                    status_links.append(f"[{status}](#{anchor}){{: .md-button }}")
                f.write(" ".join(status_links) + "\n\n")

            f.write("---\n\n")

            # Render the specific tables
            for status in ordered_statuses:
                f.write(f"## {status}\n\n")
                f.write("| TIP | Title | Author | Category |\n")
                f.write("| :--- | :--- | :--- | :--- |\n")
                
                def sort_key(x):
                    nums = re.findall(r'\d+', str(x['id']))
                    return int(nums[0]) if nums else 999999
                        
                sorted_items = sorted(status_dict[status], key=sort_key)
                
                for item in sorted_items:
                    f.write(f"| {item['id']} | [{item['title']}]({item['link']}) | {item['author']} | {item['category']} |\n")
                f.write("\n")

if __name__ == "__main__":
    sync_and_build()