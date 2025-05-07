import os
import json
import argparse
from typing import Optional, List, Dict, Tuple, Any
import math
from plotly import graph_objects as go


def plot_sankey(
    json_path: str,
    output_html: Optional[str] = None,
    color_scheme: str = "standard"
) -> str:
    """
    Reads financial bucket JSON and renders a comprehensive financial Sankey diagram
    showing the flow of money through the business.
    
    Parameters:
    -----------
    json_path : str
        Path to the financial buckets JSON file
    output_html : Optional[str]
        Path to save the output HTML file (defaults to input filename + '_sankey.html')
    color_scheme : str
        Color scheme to use ('standard', 'professional', 'high_contrast')
        
    Returns:
    --------
    str : Path to the saved HTML file
    """
    # Load buckets
    with open(json_path, 'r', encoding='utf-8') as f:
        buckets_raw = json.load(f)

    # Prepare data structures
    bucket_values = {}
    bucket_display = {}
    valid_items = []
    
    # Process and validate buckets
    for item in buckets_raw:
        name = item.get('bucket')
        val = item.get('value')
        if isinstance(name, str) and isinstance(val, (int, float)) and not math.isnan(val):
            disp = abs(val)  # Use absolute values for display
            # Avoid zero sizes in visualization
            bucket_values[name] = val
            bucket_display[name] = max(disp, 1e-9)  # Minimum size for visibility
            valid_items.append(name)
    
    # Create any derived or calculated items needed for the Sankey
    derived_items = {}
    
    # Calculate EBIT (Earnings Before Interest and Taxes) if not present
    if 'Operating Income' in bucket_values and 'EBIT' not in bucket_values:
        ebit_value = bucket_values['Operating Income']
        if 'Other Income/Expense' in bucket_values:
            ebit_value += bucket_values['Other Income/Expense']
        derived_items['EBIT'] = ebit_value
        bucket_display['EBIT'] = abs(ebit_value) if abs(ebit_value) > 1e-9 else 1e-9
        valid_items.append('EBIT')
    
    # Calculate EBT (Earnings Before Taxes) if not present
    if ('EBIT' in bucket_values or 'EBIT' in derived_items) and 'EBT' not in bucket_values:
        ebit_value = derived_items.get('EBIT', bucket_values.get('EBIT', 0))
        ebt_value = ebit_value
        if 'Interest Income' in bucket_values:
            ebt_value += bucket_values['Interest Income']
        if 'Interest Expense' in bucket_values:
            ebt_value -= bucket_values['Interest Expense']
        derived_items['EBT'] = ebt_value
        bucket_display['EBT'] = abs(ebt_value) if abs(ebt_value) > 1e-9 else 1e-9
        valid_items.append('EBT')
    
    # Add any calculated items to the bucket values
    bucket_values.update(derived_items)
    
    # Define nodes (all unique financial items)
    nodes = valid_items
    idx = {n: i for i, n in enumerate(nodes)}
    
    # Define the financial flow connections (source → target)
    # This is the key part that makes the Sankey diagram represent financial flows correctly
    flows: List[Tuple[str, str]] = []
    
    # Function to add flow if both source and target exist
    def add_flow(src: str, tgt: str) -> None:
        if src in idx and tgt in idx:
            flows.append((src, tgt))
    
    # Create complete financial flow structure
    # Top-level revenue sources
    add_flow('Products', 'Revenue')
    add_flow('Services', 'Revenue')
    
    # Revenue allocation
    add_flow('Revenue', 'Cost of Revenue')
    add_flow('Revenue', 'Gross Profit')
    
    # Gross profit allocation
    add_flow('Gross Profit', 'Operating Expenses')
    add_flow('Gross Profit', 'Operating Income')
    
    # Operating Income flows to EBIT (either directly or through Other Income/Expense)
    if 'EBIT' in idx:
        add_flow('Operating Income', 'EBIT')
        if 'Other Income/Expense' in idx:
            add_flow('Other Income/Expense', 'EBIT')
    else:
        # If EBIT isn't calculated, connect directly to interest and taxes
        if 'Interest Income' in idx:
            add_flow('Operating Income', 'Interest Income')
        if 'Interest Expense' in idx:
            add_flow('Operating Income', 'Interest Expense')
        if 'Other Income/Expense' in idx:
            add_flow('Operating Income', 'Other Income/Expense')
    
    # EBIT to EBT with interest components
    if 'EBIT' in idx and 'EBT' in idx:
        add_flow('EBIT', 'EBT')
        if 'Interest Income' in idx:
            add_flow('Interest Income', 'EBT')
        if 'Interest Expense' in idx:
            add_flow('Interest Expense', 'EBT')
    
    # EBT to Net Income with taxes
    if 'EBT' in idx:
        add_flow('EBT', 'Net Income')
        if 'Taxes' in idx:
            add_flow('Taxes', 'Net Income')
    else:
        # Direct connection if EBT isn't calculated
        add_flow('Operating Income', 'Net Income')
        if 'Taxes' in idx:
            add_flow('Taxes', 'Net Income')
    
    # Add any other connections if needed for completeness
    if 'Interest Income' in idx and 'Net Income' in idx and ('EBIT' not in idx and 'EBT' not in idx):
        add_flow('Interest Income', 'Net Income')
    if 'Interest Expense' in idx and 'Net Income' in idx and ('EBIT' not in idx and 'EBT' not in idx):
        add_flow('Interest Expense', 'Net Income')
    
    # Build link arrays for Plotly
    link_source, link_target, link_value, link_color = [], [], [], []
    
    # Define color schemes
    color_schemes = {
        "standard": {
            "positive": "rgba(44, 160, 44, 0.6)",  # green
            "negative": "rgba(214, 39, 40, 0.6)",  # red
            "neutral": "rgba(140, 140, 140, 0.5)",  # gray
            "revenue": "rgba(31, 119, 180, 0.6)",  # blue
            "expense": "rgba(255, 127, 14, 0.6)",  # orange
            "profit": "rgba(44, 160, 44, 0.6)",    # green
            "tax": "rgba(148, 103, 189, 0.6)"      # purple
        },
        "professional": {
            "positive": "rgba(65, 151, 151, 0.7)",  # teal
            "negative": "rgba(204, 80, 62, 0.7)",   # rust
            "neutral": "rgba(120, 120, 120, 0.5)",  # gray
            "revenue": "rgba(52, 94, 141, 0.7)",    # navy
            "expense": "rgba(191, 129, 45, 0.7)",   # amber
            "profit": "rgba(39, 123, 69, 0.7)",     # forest green
            "tax": "rgba(142, 85, 153, 0.7)"        # violet
        },
        "high_contrast": {
            "positive": "rgba(0, 128, 0, 0.8)",     # bright green
            "negative": "rgba(220, 20, 60, 0.8)",   # crimson
            "neutral": "rgba(70, 70, 70, 0.7)",     # dark gray
            "revenue": "rgba(0, 0, 205, 0.8)",      # medium blue
            "expense": "rgba(255, 140, 0, 0.8)",    # dark orange
            "profit": "rgba(50, 205, 50, 0.8)",     # lime green
            "tax": "rgba(138, 43, 226, 0.8)"        # blue violet
        }
    }
    
    # Use the selected color scheme (default to standard if not found)
    colors = color_schemes.get(color_scheme, color_schemes["standard"])
    
    # Process each flow
    for src, tgt in flows:
        # Use absolute value for link thickness
        val = bucket_display.get(tgt, 0)
        if val <= 1e-9:
            continue
            
        link_source.append(idx[src])
        link_target.append(idx[tgt])
        link_value.append(val)
        
        # Determine link color based on financial meaning
        # Revenue generation
        if src in ['Products', 'Services'] and tgt == 'Revenue':
            link_color.append(colors["revenue"])
        # Cost allocation
        elif tgt in ['Cost of Revenue', 'Operating Expenses']:
            link_color.append(colors["expense"])
        # Profit generation
        elif tgt in ['Gross Profit', 'Operating Income', 'EBIT', 'EBT']:
            link_color.append(colors["profit"])
        # Interest flows
        elif src == 'Interest Income' or tgt == 'Interest Income':
            link_color.append(colors["positive"])
        elif src == 'Interest Expense' or tgt == 'Interest Expense':
            link_color.append(colors["negative"])
        # Tax flows
        elif src == 'Taxes' or tgt == 'Taxes':
            link_color.append(colors["tax"])
        # Final income
        elif tgt == 'Net Income':
            link_color.append(colors["profit"])
        # Default
        else:
            link_color.append(colors["neutral"])
    
    # Node positions - create a logical financial flow layout
    node_x = [0.0] * len(nodes)
    node_y = [0.5] * len(nodes)
    
    # Define horizontal position levels (left to right financial flow)
    levels = {
        0.0: ['Products', 'Services'],
        0.15: ['Revenue'],
        0.3: ['Cost of Revenue', 'Gross Profit'],
        0.45: ['Operating Expenses', 'Operating Income'],
        0.6: ['EBIT', 'Other Income/Expense'],
        0.75: ['Interest Income', 'Interest Expense', 'EBT'],
        0.9: ['Taxes', 'Net Income']
    }
    
    # Assign horizontal positions
    for x, names in levels.items():
        for name in names:
            if name in idx:
                node_x[idx[name]] = x
    
    # Calculate vertical positions to prevent overlap
    # Group nodes by their x-position
    x_groups = {}
    for name, i in idx.items():
        x_pos = node_x[i]
        if x_pos not in x_groups:
            x_groups[x_pos] = []
        x_groups[x_pos].append(name)
    
    # Distribute nodes vertically within each x-position group
    for x_pos, names in x_groups.items():
        num_nodes = len(names)
        for i, name in enumerate(names):
            # Calculate vertical position with spacing
            if num_nodes > 1:
                node_y[idx[name]] = 0.1 + (i / (num_nodes - 1)) * 0.8
            else:
                node_y[idx[name]] = 0.5  # Center if only one node at this x
    
    # Format node labels with financial values in millions
    node_labels = []
    for name in nodes:
        value = bucket_values.get(name, 0)
        # Format with sign and 1 decimal place
        sign = "" if value < 0 else "+"
        if name in derived_items:
            # Add asterisk to derived values
            node_labels.append(f"{name}*<br>${sign}{value:.1f}M")
        else:
            node_labels.append(f"{name}<br>${sign}{value:.1f}M")
    
    # Node colors based on financial meaning
    node_color = []
    for name in nodes:
        value = bucket_values.get(name, 0)
        if name in ['Products', 'Services', 'Revenue']:
            node_color.append(colors["revenue"])
        elif name in ['Cost of Revenue', 'Operating Expenses', 'Interest Expense', 'Taxes']:
            node_color.append(colors["expense"])
        elif name in ['Gross Profit', 'Operating Income', 'EBIT', 'EBT', 'Net Income']:
            node_color.append(colors["profit"])
        elif name == 'Interest Income':
            node_color.append(colors["positive"])
        elif name == 'Other Income/Expense':
            # Color based on whether it's positive or negative
            if value >= 0:
                node_color.append(colors["positive"])
            else:
                node_color.append(colors["negative"])
        else:
            node_color.append(colors["neutral"])
    
    # Build Sankey diagram
    fig = go.Figure(go.Sankey(
        arrangement='snap',  # 'snap' works better than 'fixed' for financial flows
        node=dict(
            label=node_labels,
            x=node_x,
            y=node_y,
            color=node_color,
            pad=15,        # node padding
            thickness=20,  # node thickness
            line=dict(color="black", width=0.5)
        ),
        link=dict(
            source=link_source,
            target=link_target,
            value=link_value,
            color=link_color
        )
    ))
    
    # Add title and enhance layout
    title = "Financial Flow Analysis"
    # Extract filename for title
    if json_path:
        base_name = os.path.basename(json_path).split('_')[0]
        if base_name:
            title = f"{base_name.capitalize()} - Financial Flow Analysis"
    
    # Create footnote for derived values if any exist
    footnote = ""
    if derived_items:
        footnote = "* Calculated values based on reported financials"
    
    fig.update_layout(
        title=dict(
            text=title,
            font=dict(size=20, color="#333"),
            x=0.5,  # centered title
            y=0.95
        ),
        font=dict(family="Arial, sans-serif", size=12, color="#333"),
        plot_bgcolor='rgba(250,250,250,0.9)',
        annotations=[
            dict(
                text=footnote,
                showarrow=False,
                xref="paper", yref="paper",
                x=0.01, y=-0.05,
                font=dict(size=10, color="#666")
            )
        ] if footnote else []
    )
    
    # Determine output path
    out = output_html or os.path.splitext(json_path)[0] + '_sankey.html'
    fig.write_html(
        out,
        include_plotlyjs='cdn',  # Use CDN for smaller file size
        full_html=True,
        config={'displayModeBar': True, 'displaylogo': False}
    )
    
    return out


def main():
    parser = argparse.ArgumentParser(
        description='Generate a professional financial Sankey diagram from extracted financial buckets.'
    )
    parser.add_argument('--json', '-j', required=True, help='Path to financial buckets JSON file')
    parser.add_argument('--output', '-o', help='Path to save output HTML file')
    parser.add_argument(
        '--color-scheme', '-c', 
        choices=['standard', 'professional', 'high_contrast'],
        default='professional',
        help='Color scheme to use for the Sankey diagram'
    )
    args = parser.parse_args()

    html_path = plot_sankey(args.json, args.output, args.color_scheme)
    print(f"✅ Financial Sankey diagram generated successfully")
    print(f"📊 Output saved to: {html_path}")
    print(f"📋 Open this file in your browser to view the interactive visualization")

if __name__ == '__main__':
    main()