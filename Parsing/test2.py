import fitz  # PyMuPDF
import numpy as np
from sklearn.cluster import DBSCAN

def extract_fund_facts(pdf_path):
    """
    Extract Objective and Description from KiwiSaver fund fact sheets.
    
    Args:
        pdf_path (str): Path to the PDF file
        
    Returns:
        dict: Dictionary containing 'objective' and 'description'
    """
    doc = fitz.open(pdf_path)
    result = {'objective': '', 'description': ''}
    
    for page in doc:
        # Get all text blocks on the page
        blocks = page.get_text("dict")["blocks"]
        
        # Find the "Key Fund Facts" section
        key_facts_found = False
        key_facts_y = 0
        
        for b in blocks:
            if "lines" in b:
                for line in b["lines"]:
                    for span in line["spans"]:
                        if "Key Fund Facts" in span["text"]:
                            key_facts_found = True
                            key_facts_y = span["bbox"][1]
                            break
                    if key_facts_found:
                        break
                if key_facts_found:
                    break
        
        if not key_facts_found:
            continue
            
        # Now find Objective and Description below Key Fund Facts
        objective_bbox = None
        description_bbox = None
        objective_spans = []
        description_spans = []
        
        for b in blocks:
            if "lines" not in b or b["bbox"][1] < key_facts_y:
                continue
                
            for line in b["lines"]:
                for span in line["spans"]:
                    text = span["text"].strip()
                    bbox = span["bbox"]
                    
                    # Look for Objective label
                    if text.lower().startswith("objective"):
                        objective_bbox = bbox
                    # Look for Description label
                    elif text.lower().startswith("description"):
                        description_bbox = bbox
                    # Collect spans that might belong to objective or description
                    elif objective_bbox and bbox[1] >= objective_bbox[1] - 5 and bbox[1] <= objective_bbox[3] + 5:
                        objective_spans.append((bbox[0], bbox[1], span["text"]))
                    elif description_bbox and bbox[1] >= description_bbox[1] - 10 and bbox[1] <= description_bbox[3] + 10:
                        description_spans.append((bbox[0], bbox[1], span["text"]))
        
        # Process objective spans
        if objective_spans:
            # Cluster spans by y-coordinate with a tolerance of 5 points
            y_coords = np.array([[y] for _, y, _ in objective_spans])
            clustering = DBSCAN(eps=2, min_samples=2).fit(y_coords)
            labels = clustering.labels_
            
            # Group spans by cluster
            clusters = {}
            for i, (x, y, text) in enumerate(objective_spans):
                if labels[i] not in clusters:
                    clusters[labels[i]] = []
                clusters[labels[i]].append((x, text))
            
            # Sort each cluster by x-coordinate and combine text
            objective_text = []
            for cluster in clusters.values():
                cluster.sort(key=lambda x: x[0])  # Sort by x position
                cluster_text = " ".join([text for _, text in cluster])
                objective_text.append(cluster_text)
            
            result['objective'] = " ".join(objective_text).strip()
        
        # Process description spans
        if description_spans:
            # Cluster spans by y-coordinate with a tolerance of 5 points
            y_coords = np.array([[y] for _, y, _ in description_spans])
            clustering = DBSCAN(eps=2, min_samples=1).fit(y_coords)
            labels = clustering.labels_
            
            # Group spans by cluster
            clusters = {}
            for i, (x, y, text) in enumerate(description_spans):
                if labels[i] not in clusters:
                    clusters[labels[i]] = []
                clusters[labels[i]].append((x, text))
            
            # Sort each cluster by x-coordinate and combine text
            description_text = []
            for cluster in clusters.values():
                cluster.sort(key=lambda x: x[0])  # Sort by x position
                cluster_text = " ".join([text for _, text in cluster])
                description_text.append(cluster_text)
            
            result['description'] = " ".join(description_text).strip()
        
        # If we found both, we can break
        if result['objective'] and result['description']:
            break
    
    doc.close()
    return result

# Example usage
april_2025_path = r"C:\Users\mithu\Documents\MEGA\Projects\KiwiSaver Fund Performance & ESG Analyzer\Downloads\Milford_Asset\Kiwisaver_Monthly_Fact_Sheets\New folder\zKiwiSaver_Active_Growth_Fund_April_2025.pdf"
august_2024_path = r"C:\Users\mithu\Documents\MEGA\Projects\KiwiSaver Fund Performance & ESG Analyzer\Downloads\Milford_Asset\Kiwisaver_Monthly_Fact_Sheets\New folder\KiwiSaver_Active_Growth_Fund_August_2024.pdf"

april_2025_data = extract_fund_facts(april_2025_path)
august_2024_data = extract_fund_facts(august_2024_path)

print("April 2025 Fund Facts:")
print(f"Objective: {april_2025_data['objective']}")
print(f"Description: {april_2025_data['description']}\n")

print("August 2024 Fund Facts:")
print(f"Objective: {august_2024_data['objective']}")
print(f"Description: {august_2024_data['description']}")

