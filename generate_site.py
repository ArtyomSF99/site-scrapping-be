import os
import random
from playwright.sync_api import sync_playwright
from PIL import Image
from io import BytesIO
import numpy as np
from sklearn.cluster import KMeans
import shutil
import requests
from urllib.parse import urljoin, unquote
from bs4 import BeautifulSoup
import re
import openai
from dotenv import load_dotenv
import sys
import uuid
from constants import font_styles
import base64
from urllib.parse import urlparse
import time
import imghdr
import json

load_dotenv()

# Check if a URL argument is provided in the command line
if len(sys.argv) < 2:
    print("Please provide a URL as a command line argument.")
    sys.exit(1)

url = sys.argv[1]
new_site_folder_name = sys.argv[2]
title = sys.argv[3]
template = sys.argv[4]
font = sys.argv[5]
base_url = os.getenv("BASE_URL")
openai.api_key = os.getenv("OPENAI_API_KEY")
initial_directory = os.getcwd()
logo_path = ""
logo_extension = ""
global_soup = ""
html_file_name = "index.html"
assets_folder_name = "assets"
static_folder_name = "static"
js_folder_name = "js"
font_folder_name = "fonts"
css_folder_name = "css"
assets_base_url = (
    f"{base_url}/{static_folder_name}/{new_site_folder_name}/{assets_folder_name}"
)
valid_image_extensions = [".jpg", ".jpeg", ".png", ".gif", ".bmp"]
scrapped_text = ""
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36"
}


def log_error(text):
    print("\033[91m" + text + "\033[0m")


def log_success(text):
    print("\033[92m" + text + "\033[0m")


def log_info(text):
    print("\033[93m" + text + "\033[0m")


# Function to create a folder if it doesn't exist
def create_folder(folder_name):
    if not os.path.exists(folder_name):
        os.mkdir(folder_name)
        log_success(f'[SUCCESS] Folder "{folder_name}" created.')
    else:
        log_info(f'[INFO] Folder "{folder_name}" already exists.')


create_folder(static_folder_name)

os.chdir(static_folder_name)

log_info(f'[INFO] Navigate to "{static_folder_name}".')

create_folder(new_site_folder_name)

os.chdir(new_site_folder_name)

log_info(f'[INFO] Navigate to "{new_site_folder_name}".')

create_folder(assets_folder_name)
create_folder(css_folder_name)
create_folder(font_folder_name)
create_folder(js_folder_name)


# Function to extract logo URL from an HTML element
def extract_logo_from_element(element):
    # Check for src attribute (useful for img, source, etc.)
    logo_src = element.get_attribute("src")
    if logo_src:
        return logo_src

    # If no src, check for background image
    background_image = element.evaluate("el => getComputedStyle(el).backgroundImage")
    if background_image and "url(" in background_image:
        # Extract URL from the 'url()' CSS function
        return background_image.split("url(")[1].split(")")[0].strip('"').strip("'")

    return None


# Function to download and save the logo
def download_and_save_logo(base_url, logo_url, save_path="logo_extracted"):
    global logo_path
    global logo_extension
    """Download the logo from the provided URL and save it with its original format."""
    try:
        # Handle protocol-relative URLs
        if logo_url.startswith("//"):
            logo_url = "https:" + logo_url

        # Handle relative URLs
        elif not logo_url.startswith(("http:", "https:")):
            logo_url = urljoin(base_url, logo_url)

        response = requests.get(logo_url, stream=True, headers=HEADERS)
        response.raise_for_status()

        content_type = (
            response.headers.get("Content-Type", "").split("/")[1].split(";")[0]
        )

        # Determine the file extension based on the content type
        if content_type in ["jpeg", "jpg"]:
            file_extension = "jpg"
        elif content_type == "png":
            file_extension = "png"
        elif content_type == "gif":
            file_extension = "gif"
        elif content_type == "svg+xml":
            file_extension = "svg"
        else:
            file_extension = "png"  # Default to PNG if the content type is unknown

        save_path = f"{save_path}.{file_extension}"
        logo_path = f"logo.{file_extension}"
        logo_extension = file_extension

        with open(save_path, "wb") as file:
            for chunk in response.iter_content(chunk_size=8192):
                file.write(chunk)
        log_success(f"[SUCCESS] Logo saved to: {save_path}")

    except Exception as e:
        log_error(f"[ERROR] Failed to download and save logo: {e}")


# Function to extract logo source URL from a website
def extract_logo_src(url):
    log_info(f"\n[INFO] Processing URL: {url}\n")

    with sync_playwright() as p:
        log_info("[INFO] Launching browser...")
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(url)
        img_elements = page.query_selector_all("img")

        img_src_list = []

        for img_element in img_elements:
            src = img_element.get_attribute("src")
            if src:
                img_src_list.append(src)

        # Find any element with 'logo' in its class or ID
        logo_elements = page.query_selector_all(
            "[class*=logo], [id*=logo], [alt*=logo]"
        )

        log_info(
            f"[INFO] Found {len(logo_elements)} elements with 'logo' in class or ID."
        )

        for element in logo_elements:
            logo_src = extract_logo_from_element(element)
            if logo_src and not logo_src.startswith("data:image"):
                log_info(f"[INFO] Extracted logo URL: {logo_src}")
                # download_and_save_logo(url, logo_src)  # Save the logo
                browser.close()
                return logo_src

            # Also check child elements
            children = element.query_selector_all("*")  # Get all children
            for child in children:
                logo_src = extract_logo_from_element(child)
                if logo_src and not logo_src.startswith("data:image"):
                    log_info(
                        f"[INFO] Extracted logo URL from child element: {logo_src}"
                    )
                    download_and_save_logo(url, logo_src)  # Save the logo
                    browser.close()
                    return logo_src

        log_info("[INFO] No logo found in the analyzed elements.")
        browser.close()
    return None


# Function to extract image URLs from a website
def extract_image_urls_from_website(soup: BeautifulSoup):
    log_info(f"\n[INFO] Processing URL: {url}\n")
    image_urls = []
    img_tags = soup.find_all("img")
    parsed_url = urlparse(url)
    root_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
    for image in img_tags:
        src = image.get("src")
        if src:
            try:
                if src.startswith("data:image"):
                    data_parts = src.split(",")
                    if len(data_parts) == 2:
                        data_type, data_base64 = data_parts
                        ext = data_type.split(";")[0].split(":")[1]
                        ext = get_image_extension(content_type=ext, img_name="")
                        while len(data_base64) % 4 != 0:
                            data_base64 += "="
                        data = base64.b64decode(data_base64)
                        filename = f"{str(uuid.uuid4())}{ext}"

                        with open(os.path.join("assets", filename), "wb") as img_file:
                            img_file.write(data)

                        new_url = f"{assets_base_url}/{filename}"
                        image["src"] = new_url
                        del image["srcset"]

                        image_urls.append(new_url)
                    else:
                        log_error("[ERROR] Invalid data URI format")
                if not src.startswith(("http:", "https:")):
                    src = urljoin(root_url, src)
                    image_urls.append(src)
                    new_url = download_and_move_images(src, save_path="assets")
                    image["src"] = new_url
                    del image["srcset"]

                else:
                    image_urls.append(src)
                    new_url = download_and_move_images(src, save_path="assets")
                    image["src"] = new_url
                    del image["srcset"]
            except Exception as e:
                log_error(f"[ERROR] An error occurred: {e}")
    return soup


# Function to clean a filename for saving images
def clean_filename(filename):
    return re.sub(r'[\/:*?"<>|]', "_", filename)


def get_image_extension(content_type, img_name):
    _, extension = os.path.splitext(img_name)
    if extension.lower() in (
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".bmp",
        ".tiff",
        ".svg",
        ".webp",
    ):
        return extension

    if content_type is not None:
        if content_type == "image/jpeg":
            extension = ".jpg"
        elif content_type == "image/png":
            extension = ".png"
        elif content_type == "image/gif":
            extension = ".gif"
        elif content_type == "image/bmp":
            extension = ".bmp"
        elif content_type == "image/tiff":
            extension = ".tiff"
        elif content_type == "image/svg+xml":
            extension = ".svg"
        elif content_type == "image/webp":
            extension = ".webp"
        else:
            image_response = requests.get(url, headers=HEADERS)
            image_content = image_response.content
            image_type = imghdr.what(None, h=image_content)
            if image_type:
                extension = "." + image_type
            else:
                extension = ".jpg"

        return extension

    return ".jpg"


# Function to download and move images to the specified directory
def download_and_move_images(img_url, save_path="assets"):
    try:
        if img_url.startswith("data:image"):
            data_parts = img_url.split(",")
            if len(data_parts) == 2:
                data_type, data_base64 = data_parts
                ext = data_type.split(";")[0].split(":")[1]
                ext = get_image_extension(content_type=ext, img_name="")
                
                while len(data_base64) % 4 != 0:
                    data_base64 += "="
                data = base64.b64decode(data_base64)

                filename = f"{str(uuid.uuid4())}{ext}"
                with open(os.path.join("assets", filename), "wb") as img_file:
                    img_file.write(data)
                new_url = f"{assets_base_url}/{filename}"
                log_success(
                    f"[SUCCESS] Image with URL({img_url}) saved to: assets/{filename}"
                )
                return new_url
            else:
                log_error("[ERROR] Invalid data URI format")
        else:
            if not os.path.exists(save_path):
                os.makedirs(save_path)

            img_name = str(uuid.uuid4())

            response = requests.get(img_url, stream=True, headers=HEADERS)
            content_type = response.headers.get("Content-Type")
            extension = get_image_extension(content_type, img_url)
            img_save_path = os.path.join(save_path, f"{img_name}{extension}")
            with open(img_save_path, "wb") as file:
                for chunk in response.iter_content(chunk_size=8192):
                    file.write(chunk)
            log_success(
                f"[SUCCESS] Image with URL({img_url}) saved to: {img_save_path}"
            )
            return f"{assets_base_url}/{img_name}{extension}"
    except Exception as e:
        log_error(f"[ERROR] Failed to download and move image: {e}")
        return img_url


# Color extraction functions
def extract_colors_from_resized(image, n_colors, max_size=1900):
    aspect_ratio = image.width / image.height
    if image.width > image.height:
        new_width = max_size
        new_height = int(max_size / aspect_ratio)
    else:
        new_height = max_size
        new_width = int(max_size * aspect_ratio)
    resized_image = image.resize((new_width, new_height))
    return extract_colors_with_alpha(resized_image, n_colors)


# Function to extract colors from an image with alpha channel
def extract_colors_with_alpha(image, n_colors):
    image_rgba = np.array(image)
    pixels = image_rgba.reshape(-1, 4)
    if np.all(pixels[:, 3] == 255):
        pixels = pixels[:, :3]
    kmeans = KMeans(n_clusters=n_colors)
    kmeans.fit(pixels)
    colors = kmeans.cluster_centers_
    colors = colors.round(0).astype(int)
    return colors


def add_class_to_elements(element):
    unique_class = str(uuid.uuid4())
    existing_classes = element.get("class", [])
    existing_classes.append("unique-class-" + unique_class)
    element["class"] = existing_classes


# Convert RGB to HEX
def rgb_to_hex(rgb_values):
    return ["#{:02x}{:02x}{:02x}".format(r, g, b) for r, g, b in rgb_values]


def replace_font_url(url_part, new_url, css_content):
    pattern = re.compile(
        r'@font-face\s*{[^}]*?url\s*\(\s*["\'](.*?{0}.*?)["\']\s*\)[^}]*?}'.format(
            re.escape(url_part)
        ),
        re.DOTALL,
    )

    def replace_url(match):
        original_url = match.group(1)
        new_full_url = original_url.replace(url_part, new_url)
        return match.group(0).replace(original_url, new_full_url)

    updated_css_content = pattern.sub(replace_url, css_content)

    log_success(f"[SUCCESS] Font with URL({url_part}) replaced with {new_url}")
    return updated_css_content


def replace_bg_images_to_local(css_text, root_url):
    background_image_pattern = re.compile(
        r"(background|background-image)\s*:\s*url\(([^)]+)\)"
    )
    background_image_urls = []
    matches = background_image_pattern.findall(css_text)

    for property_name, bg_img_url in matches:
        bg_img_url = bg_img_url.strip("url()").strip("'").strip('"')
        background_image_urls.append(bg_img_url)

    log_info(f"[INFO] Found {len(background_image_urls)} images in css code")
    log_info("[INFO] Start downloading and replacing")

    for old_url in background_image_urls:
        if old_url:
            # Handle relative URLs
            if not old_url.startswith(("http:", "https:")) and not old_url.startswith(
                "data:image"
            ):
                old_url = urljoin(root_url, old_url)
            new_url = download_and_move_images(old_url, save_path="assets")
            if new_url:
                css_text = css_text.replace(old_url, new_url)
    return css_text


# Function to scrape text from a URL
def scrape_data_from_url(url):
    global global_soup
    try:
        # Step 1: Launching the browser and setting up the page
        with sync_playwright() as p:
            log_info("[INFO] Launching browser...")
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1920, "height": 1080})
            page = context.new_page()

            # Step 2: Navigating to the provided URL and scrolling to load content
            page.goto(url)
            scroll_interval = 0.5
            max_scroll_attempts = 30
            scroll_attempts = 0
            page.wait_for_load_state("load")
            page.wait_for_timeout(1000)

            # Step 3: Scrolling down the page to load additional content
            while scroll_attempts < max_scroll_attempts:
                page.keyboard.press("PageDown")
                page.keyboard.up("PageDown")

                time.sleep(scroll_interval)

                if page.evaluate(
                    "window.scrollY + window.innerHeight >= document.body.scrollHeight"
                ):
                    break

                scroll_attempts += 1

            # Step 4: Handling elements related to cookies
            elements_with_cookies = page.query_selector_all(':text("cookies")')

            if elements_with_cookies:
                # Iterating through elements and removing them
                for element in elements_with_cookies:
                    current_element = element
                    iteration_count = 0
                    try:
                        # Finding and removing parent elements
                        while True:
                            parent = current_element.query_selector("xpath=..")
                            if (
                                parent
                                and parent.evaluate("(element) => element.tagName")
                                != "BODY"
                                and iteration_count < 5
                            ):
                                current_element = parent
                                iteration_count += 1
                            else:
                                break
                    except Exception as e:
                        print(f"An error occurred: {str(e)}")

                    # Removing the identified element
                    if current_element:
                        try:
                            current_element.evaluate("(element) => element.remove()")
                        except Exception as e:
                            print(
                                f"An error occurred while removing the element: {str(e)}"
                            )
            # Scroll to the beginning so that elements like navbar are not hidden
            page.evaluate("window.scrollTo(0, 0)")
            page.wait_for_timeout(1000)
            html = page.content()
            soup = BeautifulSoup(html, "html.parser")

            # Step 5: Remove lazy loading from images in the HTML content
            images_with_loading_and_display_none = soup.find_all(
                lambda tag: tag.get("loading") and tag.get("style") == "display: none;"
            )
            for image in images_with_loading_and_display_none:
                del image["loading"]
                del image["style"]

            page.wait_for_timeout(1000)

            # Step 6: Taking a full-page screenshot and saving it
            screenshot = page.screenshot(path="screenshot.png", full_page=True)
            image = Image.open(BytesIO(screenshot))
            image.save("screensht.png")

            # Step 7: Parsing the root URL from the provided URL
            parsed_url = urlparse(url)
            root_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
            base_tag = soup.find("base")

            if base_tag:
                root_url = base_tag.get("href")

            # Step 8: Handling script and font tags
            if soup is not None:
                js_elements = soup.find_all(
                    "link", href=lambda href: href and (href.endswith(".js") or ".js" in href)
                )
            else:
                log_error("[ERROR] soup is None, skipping js_elements extraction")

            font_elements = soup.find_all(
                "link",
                href=lambda href: href
                and href.endswith((".ttf", ".otf", ".woff", ".woff2", ".eot")),
            )

            font_names = []

            # Step 9: Save and replace the js with a local one
            for js_element in js_elements:
                try:
                    href = js_element.get("href")
                    if not href.startswith(("http:", "https:")):
                        href = urljoin(root_url, href)
                    response = requests.get(href, stream=False, headers=HEADERS)
                    response.raise_for_status()
                    new_filename = str(uuid.uuid4()) + ".js"

                    js_text = response.text
                    js_save_path = os.path.join(js_folder_name, f"{new_filename}")

                    with open(js_save_path, "w", encoding="utf-8") as file:
                        file.write(js_text)

                    full_link = f"{base_url}/{static_folder_name}/{new_site_folder_name}/{js_folder_name}/{new_filename}"
                    js_element["href"] = f"{full_link}"

                except Exception as e:
                    log_error(f"[ERROR] Failed to load JS: {e}")

            # Step 9: Save and replace the fonts with a local one
            for font_element in font_elements:
                try:
                    href = font_element.get("href")
                    if not href.startswith(("http:", "https:")):
                        href = urljoin(root_url, href)
                    response = requests.get(href, stream=False, headers=HEADERS)
                    response.raise_for_status()
                    url_path = urlparse(href).path
                    font_filename = os.path.basename(url_path)
                    font_save_path = os.path.join(font_folder_name, f"{font_filename}")
                    with open(font_save_path, "wb") as font_file:
                        font_file.write(response.content)
                    log_success(
                        f"[SUCCESS] Font file with URL({href}) saved to: {font_save_path}"
                    )
                    full_link = f"{base_url}/{static_folder_name}/{new_site_folder_name}/{font_folder_name}/{font_filename}"
                    font_element["href"] = f"{full_link}"
                    font_names.append(font_filename)

                except Exception as e:
                    log_error(f"[ERROR] Failed to load Font: {e}")

            script_tags = soup.find_all("script")

            pattern = re.compile(
                r'createElement\("script"\).+?src=["\'](https://.+?)["\']'
            )

            # Step 10: Find scripts that create other scripts within themselves with a link to external sources
            for script_tag in script_tags:
                script_tag["crossorigin"] = "anonymous"
                try:
                    href = script_tag.get("src")
                    if href:
                        if not href.startswith(("http:", "https:")):
                            href = urljoin(root_url, href)
                        response = requests.get(href, stream=False, headers=HEADERS)
                        response.raise_for_status()
                        js_filename = str(uuid.uuid4()) + ".js"
                        js_pattern = r'createElement\("script"\);'
                        js_text = response.text
                        js_text = re.sub(js_pattern, "", js_text)
                        js_save_path = os.path.join(js_folder_name, f"{js_filename}")
                        with open(js_save_path, "w", encoding="utf-8") as js_file:
                            js_file.write(js_text)
                        log_success(
                            f"[SUCCESS] JS file with URL({href}) saved to: {js_save_path}"
                        )
                        full_link = f"{base_url}/{static_folder_name}/{new_site_folder_name}/{js_folder_name}/{js_filename}"
                        script_tag["src"] = f"{full_link}"

                except Exception as e:
                    log_error(f"[ERROR] Failed to load JS: {e}")

                script_content = script_tag.string

                if script_content:
                    match = pattern.search(script_content)
                    if match:
                        print(match)
                        src = match.group(1)
                        if src.startswith("https"):
                            script_tag.extract()

            body_tag = soup.body

            # remove_empty_divs(body_tag)

            for element in body_tag.find_all():
                add_class_to_elements(element)

            css_links = soup.find_all(
                "link",
                href=lambda href: href and (href.endswith(".css") or ".css" in href),
            )

            # Step 11: Find the font url inside the css and replace them with local ones then save the new css
            for css_tag in css_links:
                try:
                    href = css_tag.get("href")
                    if href:
                        if not href.startswith(("http:", "https:")):
                            href = urljoin(root_url, href)
                        response = requests.get(href, stream=False, headers=HEADERS)
                        response.raise_for_status()
                        filename = str(uuid.uuid4()) + ".css"

                        css_text = response.text
                        css_text = replace_bg_images_to_local(css_text, root_url)

                        pattern = re.compile(
                            r"@font-face\s*{[^}]*?url\s*\(\s*['\"]?(.*?)['\"]?\s*\)[^}]*?}",
                            re.DOTALL,
                        )

                        matches = pattern.findall(css_text)

                        for font_name in font_names:
                            for i in range(len(matches)):
                                if font_name in matches[i]:
                                    css_text = css_text.replace(
                                        matches[i], f"../fonts/{font_name}"
                                    )

                        css_save_path = os.path.join(css_folder_name, f"{filename}")
                        while len(css_text) % 4 != 0:
                            css_text += "="
                        with open(css_save_path, "w", encoding="utf-8") as css_file:
                            css_file.write(css_text)
                        full_link = f"{base_url}/{static_folder_name}/{new_site_folder_name}/{css_folder_name}/{filename}"
                        css_tag["href"] = f"{full_link}"
                        log_success(
                            f"[SUCCESS] CSS file with URL({href}) saved to: {css_save_path}"
                        )
                except Exception as e:
                    log_error(f"[ERROR] Failed to download and save CSS file: {e}")

            head_tag = soup.head

            # Step 12: Find all global styles and save them
            try:
                page.wait_for_timeout(3000)

                all_styles = page.evaluate(
                    """
                    () => {
                        const styleSheets = Array.from(document.styleSheets);
                        const cssTextArray = [];

                        styleSheets.forEach(sheet => {
                        try {
                            const cssRules = Array.from(sheet.cssRules);
                            cssRules.forEach(rule => {
                            cssTextArray.push(rule.cssText);
                            });
                        } catch (e) {
                            // Handle the exception if needed
                        }
                        });

                        return cssTextArray;
                    }
                    """
                )
                all_styles_text = "\n".join(all_styles)
                all_styles_text = replace_bg_images_to_local(all_styles_text, root_url)

                all_css_file_name = "global-" + str(uuid.uuid4()) + ".css"
                all_css_file_path = os.path.join(
                    css_folder_name, f"{all_css_file_name}"
                )

                with open(all_css_file_path, "w", encoding="utf-8") as css_file:
                    css_file.write(all_styles_text)
                full_link = f"{base_url}/{static_folder_name}/{new_site_folder_name}/{css_folder_name}/{all_css_file_name}"
                new_link_tag = soup.new_tag(
                    "link", rel="stylesheet", href=unquote(full_link)
                )

                head_tag.append(new_link_tag)

            except Exception as e:
                log_error(f"[ERROR] Failed to add CSS link: {e}")

            # Step 13: Find the background image url inside the inline styles and replace
            for tag in soup.find_all(True):
                if "style" in tag.attrs:
                    inline_style = tag["style"]
                    background_image_pattern = re.compile(
                        r"url\(['\"]?([^)]+?)['\"]?\)"
                    )
                    matches = background_image_pattern.findall(inline_style)

                    for old_url in matches:
                        parsed_url = urlparse(url)
                        formatted_url = old_url
                        if old_url:
                            # Handle relative URLs
                            if not old_url.startswith(
                                ("http:", "https:")
                            ) and not old_url.startswith("data:image"):
                                formatted_url = urljoin(root_url, old_url)
                        new_url = download_and_move_images(
                            formatted_url, save_path="assets"
                        )
                        if new_url:
                            tag["style"] = tag["style"].replace(old_url, new_url)

            for button in soup.find_all("button"):
                del button["href"]

            for a in soup.find_all("a"):
                del a["href"]

            for source_tag in soup.find_all("source"):
                source_tag.decompose()

            global_soup = soup

            return soup

    except requests.exceptions.RequestException as e:
        log_error(f"[ERORR] with request:, {e}")
    except Exception as e:
        log_error(f"[ERROR]: {e}")


def scrape_text_from_url(url):
    global global_soup
    try:
        with sync_playwright() as p:
            log_info("[INFO] Launching browser...")
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1920, "height": 1080})
            page = context.new_page()

            page.goto(url)
            scroll_interval = 0.5
            max_scroll_attempts = 30

            scroll_attempts = 0
            page.wait_for_load_state("load")
            page.wait_for_timeout(1000)
            while scroll_attempts < max_scroll_attempts:
                page.keyboard.press("PageDown")
                page.keyboard.up("PageDown")

                time.sleep(scroll_interval)

                if page.evaluate(
                    "window.scrollY + window.innerHeight >= document.body.scrollHeight"
                ):
                    break

                scroll_attempts += 1
            page.wait_for_timeout(1000)
            page.evaluate("window.scrollTo(0, 0)")

            html = page.content()
            soup = BeautifulSoup(html, "html.parser")
            images_with_loading_and_display_none = soup.find_all(
                lambda tag: tag.get("loading") and tag.get("style") == "display: none;"
            )
            for image in images_with_loading_and_display_none:
                del image["loading"]
                del image["style"]
            page.wait_for_timeout(5000)
            screenshot = page.screenshot(path="screenshot.png", full_page=True)
            image = Image.open(BytesIO(screenshot))
            image.save("screensht.png")
            style_tags = soup.find_all("style", attrs={"data-styled": True})

            log_info("[CSS]" + style_tags)
            for script_tag in soup.find_all("script"):
                script_tag.extract()

            global_soup = soup
            text = soup.get_text()
            words = re.findall(r"[A-Z][a-z]*", text)
            formatted_text = " ".join(words)

            return formatted_text

    except requests.exceptions.RequestException as e:
        log_error(f"[ERORR] with request:, {e}")
    except Exception as e:
        log_error(f"[ERROR]: {e}")


# Scrape text from the provided URL
if template == "0":
    global_soup = scrape_data_from_url(url)
elif template == "1":
    scrapped_text = scrape_text_from_url(url)


# Main function to extract colors from a website
def extract_colors_from_website(url):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(url)
        screenshot = page.screenshot()
        browser.close()

    image = Image.open(BytesIO(screenshot))

    # Extract colors from top 5% of the image for the header
    header_colors = extract_colors_from_resized(
        image.crop((0, 0, image.width, int(image.height * 0.05))), 2
    )
    background_color = extract_colors_from_resized(image, 1)
    palette_colors = extract_colors_from_resized(image, 4)

    return (
        rgb_to_hex(header_colors),
        rgb_to_hex(background_color),
        rgb_to_hex(palette_colors),
    )


# Function to determine contrasting text color for a given background color.
# The function takes a background color in hexadecimal format and returns the contrasting text color (either black or white).
def get_header_text_color(hex_color):
    # Remove the '#' character from the beginning of the hex color
    hex_color = hex_color[0].lstrip("#")

    # Convert the hex color to an RGB integer
    rgb = int(hex_color, 16)

    # Calculate the inverted RGB color by subtracting from white (0xFFFFFF)
    inverted_rgb = 0xFFFFFF - rgb

    # Determine whether to use black or white text based on the inverted RGB color
    if inverted_rgb <= 0xFFFFFF / 2:
        inverted_hex = "#000000"  # Use Black text
    else:
        inverted_hex = "#FFFFFF"  # Use White text

    # Return the inverted hex color as a list
    return [inverted_hex]


# Call the color extraction function and logo extraction function
header_colors = []
background_color = []
palette_colors = []
header_text_color = []
if template == "1":
    header_colors, background_color, palette_colors = extract_colors_from_website(url)
    header_text_color = get_header_text_color([header_colors[0]])
    extract_logo_src(url)

    # Print the extracted colors
    log_info("\nExtracted Colors:")
    log_info(f"Header Colors: {header_colors}")
    log_info(f"Header Text Color: {header_text_color}")
    log_info(f"Background Color: {background_color}")
    log_info(f"Palette of 4 Colors: {palette_colors}")
    log_info("\n")

# Get the current working directory
print(os.getcwd())

if template == "1":
    try:
        # Correct the paths considering your script's execution context
        source_path = os.path.join(os.getcwd(), f"./logo_extracted.{logo_extension}")
        destination_path = os.path.join(os.getcwd(), f"assets/{logo_path}")

        # Move the logo to the assets folder
        shutil.move(source_path, destination_path)
    except Exception as e:
        log_error(f"[ERROR] An error occurred while moving the logo: {e}")

        # If there is an error, copy "no_logo.png" to assets folder and rename it to "logo.png"
        script_directory = os.path.dirname(os.path.abspath(__file__))
        no_logo_source = os.path.join(script_directory, "../../no_logo.png")
        no_logo_destination = os.path.join(os.getcwd(), "assets/logo.png")

        try:
            shutil.copy(no_logo_source, no_logo_destination)
            log_success("[SUCCESS] Copied 'no_logo.png' to assets folder as 'logo.png'")
        except Exception as e:
            log_error(f"[ERRORR] An error occurred while copying 'no_logo.png': {e}")


def remove_empty_divs(soup):
    for div in soup.find_all("div"):
        if not div.contents:
            div.extract()
        else:
            remove_empty_divs(div)


def add_unique_class_to_body(html):
    soup = BeautifulSoup(html, "html.parser")
    global soup_with_unique_classes
    soup_with_unique_classes = soup

    for element in soup_with_unique_classes.body.find_all():
        unique_class = str(uuid.uuid4())
        existing_classes = element.get("class", [])
        existing_classes.append("unique-class-" + unique_class)
        element["class"] = existing_classes


# Function to perform text summarization
def text_summarization(text):
    # Comment this part to To save time and tokens during development
    # chat_completion = openai.ChatCompletion.create(model="gpt-3.5-turbo", messages=[{"role": "user", "content": f"""Here is text scrapped from website.
    # You're an experienced marketer.
    # Analyse the text and tell what it is about.
    # Maximum 10 lines
    # Without your comments.
    # Here is text: {text}"""}])
    # return chat_completion.choices[0].message.content
    return "RANDOM TEXT RANDOM TEXT RANDOM TEXT RANDOM TEXT RANDOM TEXT RANDOM TEXT RANDOM TEXT RANDOM TEXT RANDOM TEXT RANDOM TEXT RANDOM TEXT RANDOM TEXT RANDOM TEXT RANDOM TEXT RANDOM TEXT RANDOM TEXT RANDOM TEXT RANDOM TEXT"


# Perform text summarization using AI
ai_generated_text = text_summarization(scrapped_text)


# Function to get a random image from the assets directory
def get_random_image_from_assets(directory="assets"):
    images = [
        f
        for f in os.listdir(directory)
        if os.path.isfile(os.path.join(directory, f))
        and f.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".svg"))
    ]
    return random.choice(images)


# Function to get a heaviest image from the assets directory
def get_heaviest_image_from_assets(directory="assets"):
    images = [
        f
        for f in os.listdir(directory)
        if os.path.isfile(os.path.join(directory, f))
        and f.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".svg"))
    ]

    if not images:
        return None

    heaviest_image = None
    heaviest_size = 0

    for image in images:
        image_path = os.path.join(directory, image)
        size = os.path.getsize(image_path)
        if size > heaviest_size:
            heaviest_size = size
            heaviest_image = image

    return heaviest_image


# Extract image URLs from the website


global_soup = extract_image_urls_from_website(global_soup)

# Download and move images to the assets folder
# download_and_move_images(image_urls, save_path="assets")

# Get a random image from the assets directory
random_image = get_heaviest_image_from_assets()


log_info(f"[INFO] Selected random image: {random_image}")


# Create the HTML content for the website
html_content = ""
if template == "1":
    template_1_flex_container = f"""<div class="flex-container">
                    <div class="text-column">
                        <span class="title">{title}</span>
                        <p class="text-content">{ai_generated_text}</p>
                    </div>
                    <div class="image-column">
                        <img class="random-image" src="{assets_base_url}/{random_image}" style="max-width: 400px; max-height: 400px;"/>
                    </div>
                </div>"""

    template_2_flex_container = f"""<div class="flex-container">
                        <div class="image-column">
                            <img class="random-image" src="{assets_base_url}/{random_image}" style="max-width: 400px; max-height: 400px;"/>
                        </div>
                        <div class="text-column">
                            <h2 class="title">{title}</h2>
                            <div class="text-content">{ai_generated_text}</div>
                        </div>
                    </div>"""

    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <title>Created by Tersicore</title>
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link href="https://fonts.googleapis.com/css2?family=DM+Sans:opsz@9..40&family=Nosifer&family=Playfair+Display&family=Roboto&family=Space+Grotesk&display=swap" rel="stylesheet">
        <style>
        * {{
            padding: 0;
            margin: 0;
        }}
        .container {{
            max-width: none;
            min-height: 100vh;
            height: fit-content;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            align-items: center;
            background-color: {background_color[0]} !important;
            {font_styles[font]}
        }}
        header.site-header {{
            box-sizing: border-box;
            display: flex;
            justify-content: center;
            background-color: {header_colors[0]} !important;
            border: none !important;
            padding: 30px 20px !important;
            width: 100%;
        }}
        .site-header .wrapper{{
            display: flex;
            max-width: 1200px;
            width: 100%;
            justify-content: space-between;
            color: {header_text_color[0]} !important;
        }}
        footer.site-footer {{
            box-sizing: border-box;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
            background-color: {header_colors[0]} !important;
            width: 100%;
        }}
        .site-footer .wrapper {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 30px 0 !important;
            max-width: 1200px;
            width: 100%;
            color: {header_text_color[0]} !important;
        }}
        .footer-content {{
            flex: 1;
            color: {header_text_color[0]} !important;
        }}
        .content {{
            display: flex;
            flex-direction: column;
            align-items: center;
            row-gap: 60px;
            padding: 60px 20px; 
            background-color: {background_color[0]} !important;
        }}
        .flex-container {{
            flex: 1;
            display: flex;
            justify-content: space-between;
            max-width: 1200px;
            width: 100%;
            column-gap: 60px;
            flex-wrap: wrap;
        }}
        .text-column, .image-column {{
            flex: 1;
            padding: 15px;
        }}
        .title {{
            color: {header_colors[0]};
            font-size: 32px;
            font-weight: 500;
        }}
        .text-content {{
            margin-top: 40px;
        }}
        .btn-box{{
            display: flex;
            align-items: center;
        }}
        .footer-content p {{
            cursor: pointer;
            color: {header_text_color[0]} !important;
        }}
        .order-btn {{
            padding: 14px 30px;
            background-color: {header_colors[0]};
            border: none;
            border-radius: 4px;
            font-size: 18px;
            cursor: pointer;
            color: {header_text_color[0]} !important;
        }}
        </style>
    </head>
    <body>
        <div class="container">
            <header class="site-header">
                <div class="wrapper">
                    <a href="{url}">
                        <img src="{assets_base_url}/{logo_path}" alt="Logo" style="max-width: 200px; max-height: 50px;">
                    </a>
                    <div class="btn-box">
                        <a href="{url}">
                            <span>GO TO WEBSITE</span>
                        </a>
                        <span style="margin-left: 30px; cursor: pointer;">ORDER NOW</span>
                    <div>
                </div>
            </header>
            <div class="content">
                {template_1_flex_container if template == "1" else template_2_flex_container}
                <button class="order-btn">ORDER NOW</button>
            </div>
            <footer class="site-footer">
                <div class="wrapper">
                    <div style="display: flex; justify-content: space-between; width: 100%; column-gap: 70px;">
                        <div style="align-self: center;">
                            <a href="{url}">
                            <img src="{assets_base_url}/{logo_path}" alt="Logo" style="max-width: 200px; max-height: 50px;"/>
                            </a>
                        </div>
                        <div class="footer-content">
                            <p><b>Address:</b></p>
                            <p>123 Main Street,</p>
                            <p>Cityville, State 12345</p>
                            <p style="margin-top: 16px;"><b>Working Hours:</b></p>
                            <p>Monday: 9:00 AM - 6:00 PM</p>
                            <p>Tuesday: 9:00 AM - 6:00 PM</p>
                            <p>Wednesday: 9:00 AM - 6:00 PM</p>
                            <p>Thursday: 9:00 AM - 8:00 PM</p>
                            <p>Friday: 9:00 AM - 8:00 PM</p>
                            <p>Saturday: 10:00 AM - 4:00 PM</p>
                            <p>Sunday: Closed</p>
                        </div>
                        <div>
                            <span style="cursor: pointer;">CONTACT US</span>
                        </div>
                    </div>
                </div>
            </footer>
        </div>
    </body>
    </html>
    """

    add_unique_class_to_body(html_content)

# Create the HTML file with the generated content if template is not '0'
if template == "0":
    with open("index.html", "w", encoding="utf-8") as file:
        file.write(global_soup.prettify())
elif template == "1":
    with open(f"{html_file_name}", "w", encoding="utf-8") as html_file:
        html_file.write(str(soup_with_unique_classes))

log_success("[SUCCESS] Site created successfully!")
