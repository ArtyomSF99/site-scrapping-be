from bs4 import BeautifulSoup
import sys
from constants import font_styles

if len(sys.argv) < 2:
    print("Please provide command line arguments.")
    sys.exit(1)

folder_name = sys.argv[1]
template = sys.argv[2]
font = sys.argv[3]

# Specify the path to your local HTML file
html_file_path = f"static/{folder_name}/index.html"

# Open and read the local HTML file
with open(html_file_path, "r") as file:
    html = file.read()

# Parsing HTML using BeautifulSoup
soup = BeautifulSoup(html, "html.parser")

# Find the 'container' div in the HTML
container = soup.find('div', class_='container')
if font != '0':
    container['style'] = font_styles[font]

# Find the 'flex-container' div in the HTML
flex_container = soup.find("div", class_="flex-container")

# Find 'image-column' and 'text-column' blocks within the 'flex-container'
image_column = flex_container.find("div", class_="image-column")
text_column = flex_container.find("div", class_="text-column")

# If the 'template' is 1, swap the positions of 'image-column' and 'text-column'
if template == '1':
    image_column.insert_before(text_column)
# If the 'template' is 2, leave the order unchanged
elif template == '2':
    image_column.insert_after(text_column)

# Save the modified HTML code to a file or print it to the screen
with open(f"static/{folder_name}/index.html", "w") as file:
    file.write(str(soup))
