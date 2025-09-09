from playwright.sync_api import sync_playwright
import re
import pandas as pd

def extract_fisher_funds_chart_data():
    with sync_playwright() as p:
        # Launch the browser
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        
        # Navigate to the page
        page.goto("https://fisherfunds.co.nz/funds-and-performance/property-and-infrastructure-fund/performance", timeout=60000)
        
        # Wait for the chart to load
        page.wait_for_selector('.recharts-responsive-container.line-chart', timeout=10000)
        
        # Extract the SVG element
        svg = page.query_selector('.recharts-surface')
        if not svg:
            print("Could not find SVG element")
            browser.close()
            return None
        
        # Extract the dates from x-axis
        date_elements = page.query_selector_all('.xAxis .recharts-cartesian-axis-tick text')
        dates = [el.inner_text() for el in date_elements]
        
        # Extract the y-axis values (for reference)
        y_axis_elements = page.query_selector_all('.yAxis .recharts-cartesian-axis-tick text')
        y_values = [el.inner_text() for el in y_axis_elements]
        
        # Extract the data points from the SVG paths
        paths = page.query_selector_all('.recharts-area-curve')
        
        if len(paths) < 2:
            print("Could not find both data paths")
            browser.close()
            return None
        
        # Get the path data for both lines
        fund_path = paths[0].get_attribute('d')
        benchmark_path = paths[1].get_attribute('d')
        
        # Extract points from path data
        def extract_points(path_data):
            return re.findall(r'L(\d+\.?\d*),(\d+\.?\d*)', path_data)
        
        fund_points = extract_points(fund_path)
        benchmark_points = extract_points(benchmark_path)
        
        # Create a DataFrame with the extracted data
        data = {
            'Date': dates,
            'Fund_X': [float(p[0]) for p in fund_points[:len(dates)]],
            'Fund_Y': [float(p[1]) for p in fund_points[:len(dates)]],
            'Benchmark_X': [float(p[0]) for p in benchmark_points[:len(dates)]],
            'Benchmark_Y': [float(p[1]) for p in benchmark_points[:len(dates)]],
        }
        
        df = pd.DataFrame(data)
        
        # Extract y-axis pixel positions and corresponding values
        y_axis_info = []
        for el in y_axis_elements:
            # Get the y position from the transform attribute
            transform = el.get_attribute('transform')
            y_pos = float(re.search(r'y="?(\d+\.?\d*)"?', transform or '').group(1)) if transform else 0
            value = float(el.inner_text().replace('$', '').replace(',', ''))
            y_axis_info.append({'y_pos': y_pos, 'value': value})
        
        # Sort by y_pos (ascending order)
        y_axis_info.sort(key=lambda x: x['y_pos'])
        
        # Create a mapping function from pixel to value
        def map_y_to_value(y_pixel):
            # Find the two closest reference points
            for i in range(len(y_axis_info) - 1):
                y1 = y_axis_info[i]['y_pos']
                y2 = y_axis_info[i+1]['y_pos']
                if y1 <= y_pixel <= y2:
                    v1 = y_axis_info[i]['value']
                    v2 = y_axis_info[i+1]['value']
                    # Linear interpolation
                    value = v1 + (v2 - v1) * (y_pixel - y1) / (y2 - y1)
                    return value
            
            # Extrapolate if needed
            if y_pixel < y_axis_info[0]['y_pos']:
                return y_axis_info[0]['value']
            else:
                return y_axis_info[-1]['value']
        
        # Apply the mapping to our data
        df['Fund_Value'] = df['Fund_Y'].apply(map_y_to_value)
        df['Benchmark_Value'] = df['Benchmark_Y'].apply(map_y_to_value)
        
        # Keep only the columns we need
        result = df[['Date', 'Fund_Value', 'Benchmark_Value']]
        
        browser.close()
        return result

# Run the function
chart_data = extract_fisher_funds_chart_data()
print(chart_data)

# Save to CSV if you want
if chart_data is not None:
    chart_data.to_csv('fisher_funds_performance.csv', index=False)
    print("Data saved to fisher_funds_performance.csv")