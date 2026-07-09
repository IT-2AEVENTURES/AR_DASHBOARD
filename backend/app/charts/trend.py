import re
import plotly.graph_objects as go
from app.data.kpi import get_trend_data
import pandas as pd

def get_trend_figures(snapshot_id: str, filters: dict = None) -> list:
    # Invalidate cache for 7 latest periods
    df = get_trend_data(snapshot_id=snapshot_id, filters=filters)
    if df.empty:
        return []
        
    # Format date: Jan for monthly, DD-MMM for daily
    def format_date(row):
        if row['snapshot_type'] == 'monthly':
            return pd.to_datetime(row['snapshot_date']).strftime('%b')
        else:
            return pd.to_datetime(row['snapshot_date']).strftime('%d-%b')
            
    df['snapshot_date_str'] = df.apply(format_date, axis=1)
        
    # Chuẩn hóa các cột bị Excel convert sang date/serial
    # '46216' là Excel serial tương ứng với 2026-07-13 (cột 7-13)
    for col in list(df.columns):
        if re.match(r'^\d{5}$', str(col)) or re.match(r'^\d{4}-\d{2}-\d{2}', str(col)):
            # Xác định đây là cột 7_-_13 nếu cột 0_-_6 đứng liền trước
            col_idx = df.columns.index(col)
            if col_idx > 0 and df.columns[col_idx - 1] == '0_-_6':
                df = df.rename(columns={col: '7_-_13'})
    if '30_-_38' in df.columns and '30_-_37' not in df.columns:
        df['30_-_37'] = df['30_-_38']
    
    # 11 charts from the image
    charts = [
        {"col": "balance_overdue", "title": "Balance Overdue Amount", "color": "#009ef7"},
        {"col": "pct_overdue", "title": "% Overdue / Balance Overdue", "color": "#009ef7", "is_pct": True},
        {"col": "total_ar", "title": "Total AR Amount", "color": "#009ef7"},
        {"col": "60_up", "title": "Overdue 60 UP", "color": "#fd7e14"},
        {"col": "45_up", "title": "Overdue 45 UP", "color": "#fd7e14"},
        {"col": "38_-_45", "title": "Overdue 38 - 45", "color": "#fd7e14"},
        {"col": "30_-_37", "title": "Overdue 30 - 37", "color": "#009ef7"},
        {"col": "21_-_29", "title": "Overdue 21 - 29", "color": "#009ef7"},
        {"col": "14_-_20", "title": "Overdue 14 - 20", "color": "#009ef7"},
        {"col": "7_-_13",  "title": "Overdue 7 - 13",  "color": "#009ef7"},
        {"col": "0_-_6",   "title": "Overdue 0 - 6",   "color": "#009ef7"}
    ]
    
    results = []
    
    for chart in charts:
        y_data = df[chart["col"]] if chart["col"] in df.columns else pd.Series([0]*len(df))
        
        texts = []
        for v in y_data:
            if pd.isna(v): v = 0
            if chart.get("is_pct"):
                texts.append(f"{v*100:.1f}%")
            else:
                if v >= 1_000_000:
                    texts.append(f"{v/1_000_000:.1f}M")
                elif v >= 1_000:
                    texts.append(f"{v/1_000:.1f}K")
                else:
                    texts.append(f"{v:,.0f}")
        
        # Calculate headroom
        max_val = y_data.max()
        if pd.isna(max_val) or max_val == 0:
            max_val = 1
            
        fig = go.Figure()
        
        fig.add_trace(
            go.Bar(
                x=df['snapshot_date_str'],
                y=y_data,
                marker_color=chart["color"],
                text=texts,
                textposition='outside',
                textfont=dict(size=14, weight="bold"),
                cliponaxis=False,
                showlegend=False
            )
        )
        
        fig.update_layout(
            title=dict(
                text=chart["title"],
                font=dict(size=16, color="#0f172a"),
                x=0.5,
                xanchor='center'
            ),
            template="plotly_white",
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            margin=dict(t=50, b=30, l=30, r=30),
            font=dict(family="'Plus Jakarta Sans', sans-serif", color="#334155", size=13),
            height=420,
            dragmode=False # Khóa kéo thả
        )
        
        # Configure axes
        fig.update_xaxes(
            showgrid=False,
            showline=True, linewidth=1, linecolor='#cbd5e1', mirror=True,
            tickangle=0,
            tickfont=dict(color='#475569', size=12),
            fixedrange=True # Khóa Zoom X
        )
        
        tickformat = ".0%" if chart.get("is_pct") else ",.0f"
        
        fig.update_yaxes(
            range=[0, max_val * 1.35],
            showgrid=True, gridcolor='#f1f5f9',
            showline=True, linewidth=1, linecolor='#cbd5e1', mirror=True,
            showticklabels=True,
            tickformat=tickformat,
            tickfont=dict(color='#475569', size=12),
            fixedrange=True # Khóa Zoom Y
        )
        
        results.append({
            "title": chart["title"],
            "fig": fig
        })
        
    return results
