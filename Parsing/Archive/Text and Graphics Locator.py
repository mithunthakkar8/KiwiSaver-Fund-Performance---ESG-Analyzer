import fitz  # PyMuPDF

def locate_text_and_extract_graphics(pdf_path, search_text):
    doc = fitz.open(pdf_path)
    found_pages = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        text_instances = page.search_for(search_text)

        if text_instances:
            print(f"Text found on page {page_num + 1}")
            found_pages.append(page_num)

    if not found_pages:
        print("Text not found in any page.")
        return

    for page_num in found_pages:
        page = doc[page_num]
        print(f"\n--- Details for Page {page_num + 1} ---")

        # Extract all text blocks
        text_blocks = page.get_text("dict")["blocks"]
        print("\nText Blocks:")
        for block in text_blocks:
            print(f"  Block bbox: {block['bbox']}")
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    print(f"    Text: {span['text']} | Font: {span['font']} | Size: {span['size']} | BBox: {span['bbox']}")

        # Extract shapes (lines, rectangles, etc.)
        print("\nShapes:")
        for item in page.get_drawings():
            if item["type"] == "line":
                print(f"  Line from {item['points'][0]} to {item['points'][1]} | Color: {item['color']}")
            elif item["type"] == "rect":
                print(f"  Rectangle at {item['rect']} | Color: {item['color']}")
            elif item["type"] == "curve":
                print(f"  Curve points: {item['points']} | Color: {item['color']}")
            # You can expand for 'bezier', 'polyline', etc. if needed

if __name__ == "__main__":
    pdf_path = r"C:\Users\mithu\Documents\MEGA\Projects\KiwiSaver Fund Performance & ESG Analyzer\Downloads\Fisher_Funds\Kiwisaver\New folder\KiwiSaver Plan Balanced Fund Update December 2021.pdf"
    search_text = "Top 10 Investments"
    locate_text_and_extract_graphics(pdf_path, search_text)
