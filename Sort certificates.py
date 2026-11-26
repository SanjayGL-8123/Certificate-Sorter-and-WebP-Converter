"""
Sort certificates into organized folders:

    <OUTPUT>/Certificates/          Main unique certificates (PNG + WebP), sorted by topic subfolder
    <OUTPUT>/Duplicate Certificates/ Duplicate files (original copy kept here)
    <OUTPUT>/Notes/                  Non-certificate files

Each certificate is renamed by its topic (e.g., "AI Certificate", "Docker Certificate").
No Tesseract OCR needed — uses PDF text extraction + filename-based detection.

Install first:
    pip install pillow pymupdf
"""

import hashlib
import re
import shutil
import sys
from pathlib import Path

import pymupdf  # PyMuPDF 2.x
from PIL import Image

# ---- Change these settings ----
INPUT_FOLDER = Path(r"C:\Users\Sanjay G L\Desktop\convert into webp\Certificates")
OUTPUT_FOLDER = Path(r"C:\Users\Sanjay G L\Desktop\convert into webp\Certificates_sorted")
QUALITY = 85          # WebP quality 1-100
PDF_DPI = 200         # PDF page sharpness
INCLUDE_SUBFOLDERS = True
# --------------------------------

IMAGE_EXT = {".png", ".jpg", ".jpeg"}
PDF_EXT = {".pdf"}
ALL_EXT = IMAGE_EXT | PDF_EXT | {".docx"}

# Words that mean "this is a certificate" (checked in text AND filename)
CERT_WORDS = [
    "certificate", "certify", "certified", "certification",
    "appreciation", "participation", "completion", "achievement",
    "achievements", "pledge", "award", "diploma", "credential",
]

# Topic keywords -> (folder_name, display_name)
# Order matters: first match wins. Put specific topics before general ones.
TOPICS = [
    # AI & ML
    (["artificial intelligence", "ai agent", "ai-agent", "building-ai", "generative ai",
      "machine learning", "deep learning", "ai masterclass"], "AI and ML", "AI Certificate"),
    (["copilot", "microsoft copilot"], "AI and ML", "Microsoft Copilot Certificate"),

    # Cloud & DevOps
    (["kubernetes", "k8s"], "Cloud and DevOps", "Kubernetes Certificate"),
    (["docker"], "Cloud and DevOps", "Docker Certificate"),
    (["azure"], "Cloud and DevOps", "Azure Certificate"),
    (["cloud"], "Cloud and DevOps", "Cloud Computing Certificate"),
    (["celonis"], "Cloud and DevOps", "Celonis Certificate"),

    # Cybersecurity
    (["cyber security", "cybersecurity", "cyber_security", "ethical hacking",
      "kali linux", "kali_linux"], "Cyber Security", "Cyber Security Certificate"),

    # Programming Languages
    (["python"], "Programming", "Python Certificate"),
    (["java ","java_", "java for"], "Programming", "Java Certificate"),
    (["javascript", "java script", "javascript_"], "Programming", "JavaScript Certificate"),
    (["php", "mysql", "login systems"], "Programming", "PHP MySQL Certificate"),
    (["html", "css", "web development", "full stack", "fullstack"], "Web Development", "Web Development Certificate"),
    (["sql_", "sql "], "Programming", "SQL Certificate"),

    # Databases
    (["mongodb", "mongo"], "Databases", "MongoDB Certificate"),

    # Blockchain & Crypto
    (["blockchain", "cryptocurrency", "crypto"], "Blockchain", "Blockchain Certificate"),

    # Data Science
    (["data analysis", "data science", "data_analysis"], "Data Science", "Data Analysis Certificate"),

    # Design
    (["ui/ux", "ui ux", "ui-ux", "user interface", "user experience", "ibmdesign",
      "design thinking"], "Design", "UI UX Design Certificate"),

    # Google Tools
    (["google slides", "google docs", "google sheets"], "Google Tools", "Google Tools Certificate"),

    # Microsoft
    (["microsoft learn", "microsoft"], "Microsoft", "Microsoft Learn Certificate"),

    # Social & Volunteering
    (["blood donat", "blood donor", "blood camp", "blood pledge",
      "voluntary blood"], "Social Service", "Blood Donation Certificate"),
    (["nss", "national service"], "Social Service", "NSS Certificate"),
    (["my bharat", "mybharat", "my_bharat"], "Social Service", "My Bharat Certificate"),
    (["yoga"], "Social Service", "Yoga Certificate"),
    (["police", "gun camp"], "Social Service", "Police Camp Certificate"),

    # Education
    (["wadhwani"], "Education", "Wadhwani Foundation Certificate"),
    (["pravidhi"], "Education", "Pravidhi Certificate"),
    (["education certificate"], "Education", "Education Certificate"),

    # Events
    (["hackathon"], "Events", "Hackathon Certificate"),
    (["webinar"], "Events", "Webinar Certificate"),
    (["workshop"], "Events", "Workshop Certificate"),
    (["internship"], "Career", "Internship Certificate"),

    # Courses (general - keep last as fallback)
    (["course completion", "course"], "Courses", "Course Completion Certificate"),
    (["appreciation"], "Appreciation", "Appreciation Certificate"),
]


def file_hash(path):
    """SHA-256 hash to detect duplicates."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def clean_name(text):
    """Remove illegal filename characters."""
    text = re.sub(r'[\\/:*?"<>|\n\r\t]+', " ", text)
    text = re.sub(r"\s+", " ", text).strip(" .-_,")
    return text[:90]


def unique_path(folder, stem, ext):
    """Return a path that doesn't collide with existing files."""
    target = folder / f"{stem}{ext}"
    n = 2
    while target.exists():
        target = folder / f"{stem} ({n}){ext}"
        n += 1
    return target


def pdf_pages_as_images(path):
    """Return a list of PIL images, one per PDF page."""
    zoom = PDF_DPI / 72
    images = []
    with pymupdf.open(path) as doc:
        for page in doc:
            pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
            images.append(Image.frombytes("RGB", (pix.width, pix.height), pix.samples))
    return images


def pdf_direct_text(path):
    """Extract embedded text from PDF."""
    try:
        with pymupdf.open(path) as doc:
            return "\n".join(page.get_text() for page in doc)
    except Exception:
        return ""


def get_text(path):
    """Get text from PDF (embedded text). For images, return empty string."""
    if path.suffix.lower() in PDF_EXT:
        return pdf_direct_text(path)
    return ""


def is_certificate(text, filename):
    """Check if the file is a certificate based on content + filename."""
    combined = (text + " " + filename).lower()
    return any(w in combined for w in CERT_WORDS)


def find_topic(text, filename):
    """Match a topic. Returns (folder_name, display_name) or None."""
    combined = (text + " " + filename).lower()
    for keywords, folder, display in TOPICS:
        if any(k in combined for k in keywords):
            return folder, display
    return None


def build_name(text, filename):
    """Build a clean certificate name."""
    result = find_topic(text, filename)
    if result:
        return result  # (folder, display_name)
    # Fallback: use filename but clean it up
    return "Other", clean_name(filename) if len(filename) > 3 else "Certificate"


def main():
    if not INPUT_FOLDER.is_dir():
        sys.exit(f"Input folder not found: {INPUT_FOLDER}")

    # Create output structure
    certs_dir = OUTPUT_FOLDER / "Certificates"
    dups_dir = OUTPUT_FOLDER / "Duplicate Certificates"
    notes_dir = OUTPUT_FOLDER / "Notes"
    for d in (certs_dir, dups_dir, notes_dir):
        d.mkdir(parents=True, exist_ok=True)

    # Gather all files
    walker = INPUT_FOLDER.rglob("*") if INCLUDE_SUBFOLDERS else INPUT_FOLDER.iterdir()
    files = sorted(
        p for p in walker
        if p.is_file()
        and p.suffix.lower() in ALL_EXT
        and OUTPUT_FOLDER not in p.parents
    )
    print(f"Found {len(files)} files.\n")

    seen_hashes = {}       # hash -> (name, dest_path)
    cert_count = 0
    dup_count = 0
    note_count = 0
    fail_count = 0
    topic_counts = {}      # folder_name -> count

    for path in files:
        try:
            # --- Duplicate check ---
            digest = file_hash(path)
            if digest in seen_hashes:
                orig_name = seen_hashes[digest]
                # Copy duplicate to Duplicate Certificates folder
                dest = unique_path(dups_dir, path.stem, path.suffix.lower())
                shutil.copy2(path, dest)
                print(f"  DUPLICATE   {path.name}  (same as {orig_name})")
                dup_count += 1
                continue
            seen_hashes[digest] = path.name

            # --- Get text (from PDF or filename) ---
            text = get_text(path)
            filename = path.stem

            # --- Certificate or Note? ---
            if not is_certificate(text, filename):
                dest = unique_path(notes_dir, path.stem, path.suffix.lower())
                shutil.copy2(path, dest)
                print(f"  NOTE        {path.name}")
                note_count += 1
                continue

            # --- It's a certificate! Find topic and name ---
            folder_name, display_name = build_name(text, filename)
            topic_counts[folder_name] = topic_counts.get(folder_name, 0) + 1

            # Create topic subfolder
            topic_dir_png = certs_dir / folder_name / "PNG"
            topic_dir_webp = certs_dir / folder_name / "WebP"
            topic_dir_png.mkdir(parents=True, exist_ok=True)
            topic_dir_webp.mkdir(parents=True, exist_ok=True)

            # Also keep original file in topic folder
            orig_dir = certs_dir / folder_name / "Original"
            orig_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, unique_path(orig_dir, display_name, path.suffix.lower()))

            # Convert to images
            if path.suffix.lower() in PDF_EXT:
                images = pdf_pages_as_images(path)
            elif path.suffix.lower() in IMAGE_EXT:
                with Image.open(path) as im:
                    images = [im.convert("RGB")]
            else:
                # .docx - just copy original, can't convert
                print(f"  CERTIFICATE {path.name} -> {folder_name}/{display_name} (original only)")
                cert_count += 1
                continue

            # Save as PNG and WebP
            for i, img in enumerate(images, start=1):
                stem = display_name if len(images) == 1 else f"{display_name} - page {i}"
                # Add number if topic has multiple certificates
                count = topic_counts[folder_name]
                if count > 1:
                    stem = f"{stem} ({count})"

                img.save(unique_path(topic_dir_png, stem, ".png"), "PNG")
                img.save(unique_path(topic_dir_webp, stem, ".webp"), "WEBP",
                         quality=QUALITY, method=6)

            print(f"  CERTIFICATE {path.name} -> {folder_name}/{display_name}")
            cert_count += 1

        except Exception as e:
            print(f"  FAILED      {path.name}: {e}")
            fail_count += 1

    # --- Summary ---
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  Total files processed:    {len(files)}")
    print(f"  Certificates sorted:      {cert_count}")
    print(f"  Duplicates found:         {dup_count}")
    print(f"  Notes (non-certificates): {note_count}")
    print(f"  Failed:                   {fail_count}")
    print(f"\n  Output folder: {OUTPUT_FOLDER}")

    if topic_counts:
        print(f"\n  Certificate Topics:")
        for topic, count in sorted(topic_counts.items()):
            print(f"    {topic:30s} {count} certificate(s)")

    print("=" * 60)


if __name__ == "__main__":
    main()
