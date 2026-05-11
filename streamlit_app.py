"""
Streamlit Multi-Page Dashboard — 4-Page Queueing Theory System
With strict data pipeline integrity and mandatory error-checking.

🎯 Architecture:
  Page 1 (pages/1_current_metrics.py) — Upload & validate
  Page 2 (pages/2_optimization.py) — Generate recommendations  
  Page 3 (pages/3_comparison.py) — Compare with error-safe merge
  Page 4 (pages/4_simulation.py) — Monte Carlo using ONLY recommended data

🔐 Safety Rules:
  - Session state initialized on startup
  - Schema validation on all data entry points
  - Page 3 & 4 require upstream completion
  - All numeric columns validated before compute
  - No mutations of original data — always .copy()
"""

import streamlit as st
import pandas as pd
import base64
from pathlib import Path
import os
from PIL import Image

# ─────────────────────────────────────────────────────────────────────────────
# REQUIRED_COLUMNS — Data Contract (STRICT)
# ─────────────────────────────────────────────────────────────────────────────

REQUIRED_COLUMNS = [
    "time",
    "lambda",
    "mu",
    "c"
]

OPTIONAL_COLUMNS = [
    "variance"  # For M/G/1 model support
]

# ─────────────────────────────────────────────────────────────────────────────
# LOGO UTILITY FUNCTION
# ─────────────────────────────────────────────────────────────────────────────

def get_base64_image(image_path):
    """Convert image file to base64 string."""
    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode()

# ─────────────────────────────────────────────────────────────────────────────
# Session State Initialization (MANDATORY)
# ─────────────────────────────────────────────────────────────────────────────

def init_session_state():
    """Initialize all required session state keys."""
    if "df" not in st.session_state:
        st.session_state["df"] = None
    if "current_data" not in st.session_state:
        st.session_state["current_data"] = None
    if "recommended_data" not in st.session_state:
        st.session_state["recommended_data"] = None
    if "comparison_data" not in st.session_state:
        st.session_state["comparison_data"] = None
    if "simulation_results" not in st.session_state:
        st.session_state["simulation_results"] = None
    if "waste_reduction_data" not in st.session_state:
        st.session_state["waste_reduction_data"] = None
    
    # Costing parameters (NOVAMART defaults)
    if "cost_per_server_hr" not in st.session_state:
        st.session_state["cost_per_server_hr"] = 87.0  # ₱87/hr
    if "cost_per_wait_hr" not in st.session_state:
        st.session_state["cost_per_wait_hr"] = 100.0  # ₱100/hr customer time
    if "cost_per_abandonment" not in st.session_state:
        # Abandonment cost: 10% of ₱600 daily = ₱60 per abandonment
        st.session_state["cost_per_abandonment"] = 60.0  # ₱60/customer (10% × 600)


def main():
    """Initialize app and configure metadata."""
    st.set_page_config(
        page_title="Queueing Theory Dashboard",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    
    # Apply modern SaaS design system
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Poppins:wght@600;700;800&display=swap');
    
    /* Page Background */
    .main {
        background-color: #F1F5F9;
    }
    
    .block-container {
        background-color: #F1F5F9;
        padding-top: 2rem;
    }
    
    /* ─────────────────────────────────────────────────────────────────────────────
       HERO SECTION - Premium Gradient with Depth
    ───────────────────────────────────────────────────────────────────────────────*/
    .hero-section {
        background: linear-gradient(135deg, #4F46E5 0%, #6366F1 50%, #8B5CF6 100%);
        color: #FFFFFF;
        padding: 5rem 3rem;
        border-radius: 20px;
        text-align: center;
        margin-bottom: 3.5rem;
        box-shadow: 0 24px 48px rgba(79, 70, 229, 0.18), 
                    0 0 1px rgba(79, 70, 229, 0.3);
        position: relative;
        overflow: hidden;
    }
    
    .hero-section::before {
        content: '';
        position: absolute;
        top: -50%;
        right: -10%;
        width: 400px;
        height: 400px;
        background: rgba(255, 255, 255, 0.05);
        border-radius: 50%;
        filter: blur(60px);
    }
    
    .hero-section .subtitle {
        font-size: 0.875rem;
        letter-spacing: 3px;
        color: #FFFFFF;
        margin-bottom: 1rem;
        text-transform: uppercase;
        font-weight: 800;
        font-family: 'Inter', sans-serif;
    }
    
    .hero-section h1 {
        margin: 0;
        font-size: 3.5rem;
        font-weight: 900;
        line-height: 1.15;
        margin-bottom: 0.75rem;
        color: #FFFFFF;
        font-family: 'Poppins', sans-serif;
        text-shadow: 0 2px 12px rgba(0, 0, 0, 0.15);
    }
    
    .hero-section .tagline {
        font-size: 1.875rem;
        font-weight: 500;
        color: #FFFFFF;
        margin-bottom: 1.5rem;
        font-family: 'Poppins', sans-serif;
    }
    
    .hero-section .description {
        font-size: 1.125rem;
        color: #FFFFFF;
        max-width: 700px;
        margin: 0 auto 2.5rem;
        line-height: 1.8;
        font-family: 'Inter', sans-serif;
        font-weight: 500;
    }
    
    /* ─────────────────────────────────────────────────────────────────────────────
       BUTTON STYLES - Premium Accent Color Cyan
    ───────────────────────────────────────────────────────────────────────────────*/
    .button-group {
        display: flex;
        gap: 1.25rem;
        justify-content: center;
        margin-bottom: 2.5rem;
        flex-wrap: wrap;
    }
    
    /* Streamlit button wrapper styling */
    div[data-testid="stButtonContainer"] button {
        font-family: 'Inter', sans-serif;
        font-weight: 600;
        padding: 0.875rem 1.75rem !important;
        border-radius: 10px !important;
        font-size: 1rem !important;
        transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1) !important;
        border: none !important;
    }
    
    /* Primary CTA Button */
    .btn-primary {
        padding: 1rem 2.25rem;
        border-radius: 10px;
        font-weight: 700;
        font-size: 1rem;
        text-decoration: none;
        cursor: pointer;
        border: none;
        background: linear-gradient(135deg, #22D3EE 0%, #06B6D4 100%);
        color: #0F172A;
        transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
        box-shadow: 0 8px 20px rgba(34, 211, 238, 0.25);
        font-family: 'Inter', sans-serif;
    }
    
    .btn-primary:hover {
        background: linear-gradient(135deg, #06B6D4 0%, #0891B2 100%);
        box-shadow: 0 12px 32px rgba(34, 211, 238, 0.35);
        transform: translateY(-2px);
    }
    
    .btn-primary:active {
        transform: translateY(0);
        box-shadow: 0 4px 12px rgba(34, 211, 238, 0.2);
    }
    
    /* Secondary Button - Outline */
    .btn-secondary {
        padding: 1rem 2.25rem;
        border-radius: 10px;
        font-weight: 700;
        font-size: 1rem;
        text-decoration: none;
        cursor: pointer;
        border: 2px solid #22D3EE;
        background: transparent;
        color: #22D3EE;
        transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
        font-family: 'Inter', sans-serif;
    }
    
    .btn-secondary:hover {
        background: rgba(34, 211, 238, 0.1);
        border-color: #06B6D4;
        color: #06B6D4;
        box-shadow: 0 8px 20px rgba(34, 211, 238, 0.15);
    }
    
    .tags-group {
        display: flex;
        gap: 1rem;
        justify-content: center;
        flex-wrap: wrap;
        margin-top: 1.5rem;
    }
    
    .tag {
        background: #4F46E5;
        color: #FFFFFF;
        padding: 0.65rem 1.4rem;
        border-radius: 24px;
        font-size: 0.9rem;
        border: 1px solid #4F46E5;
        font-weight: 600;
        font-family: 'Inter', sans-serif;
    }
    
    /* ─────────────────────────────────────────────────────────────────────────────
       CARD COMPONENTS - Premium Style
    ───────────────────────────────────────────────────────────────────────────────*/
    
    /* Info Section Card */
    .info-section {
        background: #FFFFFF;
        padding: 2.25rem;
        border-radius: 16px;
        margin-bottom: 3.5rem;
        border: 1px solid #E2E8F0;
        display: flex;
        gap: 1.75rem;
        align-items: flex-start;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.06);
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }
    
    .info-section:hover {
        border-color: #22D3EE;
        box-shadow: 0 12px 32px rgba(34, 211, 238, 0.12);
    }
    
    .info-icon {
        font-size: 2.8rem;
        flex-shrink: 0;
        line-height: 1;
    }
    
    .info-content h3 {
        margin-top: 0;
        color: #0F172A;
        font-size: 1.3rem;
        font-weight: 700;
        font-family: 'Poppins', sans-serif;
    }
    
    .info-content p {
        margin: 0.75rem 0 0 0;
        color: #64748B;
        line-height: 1.8;
        font-size: 1rem;
        font-family: 'Inter', sans-serif;
    }
    
    /* Section Titles */
    .section-title {
        font-size: 0.8rem;
        letter-spacing: 2.5px;
        color: #64748B;
        margin-bottom: 2.25rem;
        font-weight: 800;
        text-transform: uppercase;
        font-family: 'Inter', sans-serif;
    }
    
    /* ─────────────────────────────────────────────────────────────────────────────
       WORKFLOW CARDS - Premium Design
    ───────────────────────────────────────────────────────────────────────────────*/
    
    .workflow-grid {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 2rem;
        margin-bottom: 3.5rem;
    }
    
    @media (max-width: 768px) {
        .workflow-grid {
            grid-template-columns: 1fr;
        }
    }
    
    .workflow-card {
        border: 1px solid #E2E8F0;
        border-radius: 16px;
        padding: 2.25rem;
        background: #FFFFFF;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.06);
    }
    
    .workflow-card:hover {
        border-color: #22D3EE;
        box-shadow: 0 16px 40px rgba(34, 211, 238, 0.15);
        transform: translateY(-6px);
    }
    
    .workflow-card .step-number {
        display: inline-block;
        background: linear-gradient(135deg, #CFFAFE 0%, #A5F3FC 100%);
        color: #0891B2;
        width: 56px;
        height: 56px;
        border-radius: 50%;
        line-height: 56px;
        text-align: center;
        font-weight: 800;
        font-size: 1.5rem;
        margin-bottom: 1.25rem;
        font-family: 'Poppins', sans-serif;
    }
    
    .workflow-card h3 {
        margin-top: 0;
        font-size: 1.25rem;
        color: #0F172A;
        font-weight: 700;
        font-family: 'Poppins', sans-serif;
    }
    
    .workflow-card p {
        color: #64748B;
        margin: 0.75rem 0 1.5rem 0;
        line-height: 1.8;
        font-size: 0.95rem;
        font-family: 'Inter', sans-serif;
    }
    
    .workflow-card .action-btn {
        color: #22D3EE;
        font-weight: 700;
        text-decoration: none;
        cursor: pointer;
        transition: all 0.3s;
        font-size: 0.95rem;
        font-family: 'Inter', sans-serif;
    }
    
    .workflow-card .action-btn:hover {
        color: #06B6D4;
    }
    
    /* ─────────────────────────────────────────────────────────────────────────────
       SCHEMA CARDS - Premium Grid
    ───────────────────────────────────────────────────────────────────────────────*/
    
    .schema-grid {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 1.75rem;
        margin-bottom: 3.5rem;
    }
    
    @media (max-width: 768px) {
        .schema-grid {
            grid-template-columns: repeat(2, 1fr);
        }
    }
    
    .schema-item {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 16px;
        padding: 2rem;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.06);
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }
    
    .schema-item:hover {
        border-color: #22D3EE;
        box-shadow: 0 12px 32px rgba(34, 211, 238, 0.12);
        transform: translateY(-4px);
    }
    
    .schema-item .field-name {
        font-weight: 800;
        color: #0F172A;
        margin-bottom: 0.625rem;
        font-size: 1.1rem;
        font-family: 'Poppins', sans-serif;
    }
    
    .schema-item .field-type {
        font-size: 0.8rem;
        color: #0F172A;
        margin-bottom: 0.5rem;
        font-weight: 600;
        font-family: 'Inter', sans-serif;
    }
    
    .schema-item .field-example {
        font-size: 0.85rem;
        color: #1F2937;
        font-style: italic;
        font-family: 'Inter', sans-serif;
    }
    
    /* ─────────────────────────────────────────────────────────────────────────────
       TESTIMONIALS - Premium Cards
    ───────────────────────────────────────────────────────────────────────────────*/
    
    .testimonials-grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 2rem;
        margin-bottom: 3.5rem;
    }
    
    @media (max-width: 768px) {
        .testimonials-grid {
            grid-template-columns: 1fr;
        }
    }
    
    .testimonial-card {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 16px;
        padding: 2.25rem;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.06);
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }
    
    .testimonial-card:hover {
        border-color: #22D3EE;
        box-shadow: 0 12px 32px rgba(34, 211, 238, 0.12);
        transform: translateY(-4px);
    }
    
    .testimonial-card p {
        font-style: italic;
        color: #475569;
        margin-bottom: 1.5rem;
        line-height: 1.8;
        font-size: 0.95rem;
        font-family: 'Inter', sans-serif;
    }
    
    .testimonial-card .author {
        font-size: 0.8rem;
        color: #94A3B8;
        font-weight: 700;
        font-family: 'Inter', sans-serif;
    }
    
    /* ─────────────────────────────────────────────────────────────────────────────
       CTA SECTION - Premium Call-to-Action
    ───────────────────────────────────────────────────────────────────────────────*/
    
    .cta-section {
        background: linear-gradient(135deg, #4F46E5 0%, #6366F1 50%, #8B5CF6 100%);
        color: #FFFFFF;
        padding: 4rem 3rem;
        border-radius: 20px;
        text-align: center;
        margin-top: 3.5rem;
        margin-bottom: 2rem;
        box-shadow: 0 24px 48px rgba(79, 70, 229, 0.18);
        position: relative;
        overflow: hidden;
    }
    
    .cta-section::before {
        content: '';
        position: absolute;
        top: -50%;
        right: -10%;
        width: 400px;
        height: 400px;
        background: rgba(255, 255, 255, 0.05);
        border-radius: 50%;
        filter: blur(60px);
    }
    
    .cta-section h2 {
        margin: 0 0 1rem 0;
        font-size: 2.25rem;
        font-weight: 900;
        color: #FFFFFF;
        font-family: 'Poppins', sans-serif;
        text-shadow: 0 2px 12px rgba(0, 0, 0, 0.15);
    }
    
    .cta-section p {
        margin: 0 0 2.25rem 0;
        color: #FFFFFF;
        font-size: 1.125rem;
        font-family: 'Inter', sans-serif;
        font-weight: 500;
    }
    
    /* ─────────────────────────────────────────────────────────────────────────────
       METRICS & DATA - Premium Display
    ───────────────────────────────────────────────────────────────────────────────*/
    
    [data-testid="stMetric"] {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 16px;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.06);
        padding: 1.75rem;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }
    
    [data-testid="stMetric"]:hover {
        border-color: #22D3EE;
        box-shadow: 0 12px 32px rgba(34, 211, 238, 0.12);
    }
    
    /* ─────────────────────────────────────────────────────────────────────────────
       INPUT & UPLOAD STYLING
    ───────────────────────────────────────────────────────────────────────────────*/
    
    input {
        border-radius: 12px !important;
        border: 1.5px solid #E2E8F0 !important;
        padding: 0.75rem 1rem !important;
        font-family: 'Inter', sans-serif !important;
        transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1) !important;
    }
    
    input:focus {
        border-color: #22D3EE !important;
        box-shadow: 0 0 0 3px rgba(34, 211, 238, 0.1) !important;
    }
    
    /* ─────────────────────────────────────────────────────────────────────────────
       SIDEBAR - Dark Theme Premium
    ───────────────────────────────────────────────────────────────────────────────*/
    
    [data-testid="stSidebar"] {
        background-color: #0F172A;
    }
    
    [data-testid="stSidebar"] * {
        color: #E2E8F0;
        font-family: 'Inter', sans-serif;
    }
    
    [data-testid="stSidebar"] h3 {
        color: #FFFFFF;
        font-family: 'Poppins', sans-serif;
        font-weight: 800;
    }
    
    [data-testid="stSidebar"] > div:first-child > div > div:nth-child(2) > div > div:nth-child(1) > div > button {
        background: rgba(34, 211, 238, 0.1) !important;
        border: 1px solid #22D3EE !important;
        color: #22D3EE !important;
    }
    
    /* Show sidebar collapse button with icon only, hide tooltip text */
    [data-testid="stSidebar"] button[kind="header"] {
        font-size: 1rem !important;
        padding: 0.5rem !important;
        min-width: 44px;
        display: flex;
        align-items: center;
        justify-content: center;
    }
    
    [data-testid="stSidebar"] button[kind="header"] span {
        display: none !important;
    }
    
    [data-testid="stSidebar"] button[kind="header"] svg {
        font-size: 1.25rem !important;
        display: block !important;
    }
    
    /* ─────────────────────────────────────────────────────────────────────────────
       LOGO STRIP - Horizontal Layout
    ───────────────────────────────────────────────────────────────────────────────*/
    
    .logo-strip {
        display: flex;
        gap: 28px;
        justify-content: center;
        align-items: center;
        margin-top: 24px;
        margin-bottom: 24px;
        flex-wrap: wrap;
    }
    
    .logo-item {
        height: 60px;
        width: auto;
        opacity: 0.8;
        transition: opacity 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        filter: drop-shadow(0 4px 12px rgba(0, 0, 0, 0.1));
    }
    
    .logo-item:hover {
        opacity: 1;
    }
    
    p {
        font-family: 'Inter', sans-serif;
    }
    
    h1, h2, h3, h4, h5, h6 {
        font-family: 'Poppins', sans-serif;
    }
    
    /* ─────────────────────────────────────────────────────────────────────────────
       UTILITIES
    ───────────────────────────────────────────────────────────────────────────────*/
    
    /* Divider */
    hr {
        border: none;
        border-top: 1px solid #E2E8F0;
        margin: 3.5rem 0;
    }
    
    /* Smooth transitions */
    * {
        scroll-behavior: smooth;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Initialize session state
    init_session_state()
    
    # ═════════════════════════════════════════════════════════════════════════
    # HERO SECTION
    # ═════════════════════════════════════════════════════════════════════════
    st.markdown("""
    <div class="hero-section">
        <div class="subtitle">QUEUEING THEORY OPTIMIZER</div>
        <h1>Turn Queue Data into Exact Staffing Decisions</h1>
        <div class="tagline">Stop guessing. Start optimizing.</div>
        <div class="description">
            Upload 4 columns and get precise, data-backed recommendations in minutes.
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Logo strip - perfectly centered
    col_left, col_mid, col_right = st.columns([1, 3, 1], gap="small")
    
    with col_mid:
        # Load and encode logos
        logo1_b64 = get_base64_image("logo/logo1.png")
        logo2_b64 = get_base64_image("logo/logo2.png")
        logo3_b64 = get_base64_image("logo/logo3.png")
        
        st.markdown(f"""
        <div style='display: flex; justify-content: center; align-items: center; gap: 24px; margin: 16px 0;'>
            <div style='display: flex; justify-content: center; width: 80px; height: 80px;'>
                <img src='data:image/png;base64,{logo1_b64}' style='max-width: 60px; height: auto; object-fit: contain;'>
            </div>
            <div style='display: flex; justify-content: center; width: 80px; height: 80px;'>
                <img src='data:image/png;base64,{logo2_b64}' style='max-width: 60px; height: auto; object-fit: contain;'>
            </div>
            <div style='display: flex; justify-content: center; width: 80px; height: 80px;'>
                <img src='data:image/png;base64,{logo3_b64}' style='max-width: 60px; height: auto; object-fit: contain;'>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    # Hero section buttons
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        pass
    with col2:
        if st.button("📥 Upload your CSV", key="hero_upload", use_container_width=True):
            st.switch_page("pages/1_current_metrics.py")
    with col3:
        pass
    
    st.markdown("""
    <div style="text-align: center; margin-top: 1.5rem;">
        <div class="tags-group">
            <span class="tag">M/M/1, M/M/c, M/G/1</span>
            <span class="tag">Monte Carlo simulation</span>
            <span class="tag">Only 4 columns needed</span>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # ═════════════════════════════════════════════════════════════════════════
    # INFO SECTION
    # ═════════════════════════════════════════════════════════════════════════
    st.markdown("""
    <div class="info-section">
        <div class="info-icon">⏰</div>
        <div class="info-content">
            <h3>Balancing Queues, Reducing Costs.</h3>
            <p>This system applies queueing theory to real operational data, helping managers make informed staffing decisions that reduce delays and control costs.</p>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # ═════════════════════════════════════════════════════════════════════════
    # WORKFLOW SECTION
    # ═════════════════════════════════════════════════════════════════════════
    st.markdown('<p class="section-title">THE 4-PAGE WORKFLOW</p>', unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        <div class="workflow-card">
            <div class="step-number">1</div>
            <h3>Current metrics</h3>
            <p>Upload your CSV and see your queue's true state            <img src="your-logo-url-here" alt="Logo Name" class="logo-item"> utilization, average wait, queue length, and where things are quietly breaking down.</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Explore →", key="workflow_1", use_container_width=True):
            st.switch_page("pages/1_current_metrics.py")
    
    with col2:
        st.markdown("""
        <div class="workflow-card">
            <div class="step-number">2</div>
            <h3>Optimization</h3>
            <p>The model calculates the minimum number of servers needed to hit your target wait time. No manual trial-and-error required.</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Optimize →", key="workflow_2", use_container_width=True):
            st.switch_page("pages/2_optimization.py")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        <div class="workflow-card">
            <div class="step-number">3</div>
            <h3>Simulation</h3>
            <p>Run Monte Carlo scenarios across thousands of variations. See how your queue behaves when arrival rates spike before it happens in production.</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Simulate here →", key="workflow_3", use_container_width=True):
            st.switch_page("pages/3_simulation.py")
    
    with col2:
        st.markdown("""
        <div class="workflow-card">
            <div class="step-number">4</div>
            <h3>Compare</h3>
            <p>Side-by-side view of current vs recommended. See exactly what changes, what improves, and what it means for your team's workload.</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Review →", key="workflow_4", use_container_width=True):
            st.switch_page("pages/4_comparison.py")
    
    st.markdown("---")
    
    # ═════════════════════════════════════════════════════════════════════════
    # SCHEMA SECTION
    # ═════════════════════════════════════════════════════════════════════════
    st.markdown('<p class="section-title">WHAT TO PREPARE — YOUR CSV SCHEMA</p>', unsafe_allow_html=True)
    st.markdown('<p style="color: #999; margin-bottom: 1.5rem;"><strong>4 required columns</strong> + 1 optional | <span style="color: #28a745;">Supports M/M/1, M/M/c, and M/G/1</span></p>', unsafe_allow_html=True)
    
    st.markdown("""
    <div class="schema-grid">
        <div class="schema-item">
            <div class="field-name">time</div>
            <div class="field-type">Text — interval label</div>
            <div class="field-example">e.g. 08:00–09:00</div>
        </div>
        <div class="schema-item">
            <div class="field-name">lambda</div>
            <div class="field-type">Float — arrival rate</div>
            <div class="field-example">e.g. 12.5 /min</div>
        </div>
        <div class="schema-item">
            <div class="field-name">mu</div>
            <div class="field-type">Float — service rate</div>
            <div class="field-example">e.g. 5.0 /min</div>
        </div>
        <div class="schema-item">
            <div class="field-name">c</div>
            <div class="field-type">Integer — servers</div>
            <div class="field-example">e.g. 3</div>
        </div>
        <div class="schema-item">
            <div class="field-name">variance</div>
            <div class="field-type">Float — optional (M/G/1)</div>
            <div class="field-example">e.g. 0.04</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("**Required:** time, lambda, mu, c | **Optional:** variance (for M/G/1 models with general service distributions)")

    
    st.markdown("---")
    
    # ═════════════════════════════════════════════════════════════════════════
    # TESTIMONIALS SECTION
    # ═════════════════════════════════════════════════════════════════════════
    st.markdown('<p class="section-title">WHAT USERS SAY AFTER THEIR FIRST RUN</p>', unsafe_allow_html=True)
    
    st.markdown("""
    <div class="testimonials-grid">
        <div class="testimonial-card">
            <p>"Optimizing our checkout queues didn't just reduce wait times—it completely transformed how we operate. We cut unnecessary labor costs, improved customer satisfaction, and freed up resources to invest back into the business."</p>
            <div class="author">Operations Director, Grocery Retail Group</div>
        </div>
        <div class="testimonial-card">
            <p>"The simulation page alone was worth it. We stress-tested our peak-hour setup and caught a failure mode we never would have predicted."</p>
            <div class="author">Service design analyst</div>
        </div>
        <div class="testimonial-card">
            <p>"Four columns. The compare view told us exactly what to bring to management — with numbers, not opinions."</p>
            <div class="author">Queue manager, logistics firm</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # ═════════════════════════════════════════════════════════════════════════
    # CTA SECTION
    # ═════════════════════════════════════════════════════════════════════════
    st.markdown("""
    <div class="cta-section">
        <h2>You just need to upload your data to see them</h2>
        <p>Turn your raw data into actionable queue insights upload to begin.</p>
    </div>
    """, unsafe_allow_html=True)
    
    # CTA section buttons
    col1, col2, col3, col4 = st.columns([1, 1, 1, 1])
    with col1:
        pass
    with col2:
        if st.button("📥 Upload CSV", key="cta_upload", use_container_width=True):
            st.switch_page("pages/1_current_metrics.py")
    with col3:
        pass
    with col4:
        pass
    
    # ═════════════════════════════════════════════════════════════════════════
    # SIDEBAR
    # ═════════════════════════════════════════════════════════════════════════
    st.sidebar.markdown("### 📊 Queueing Theory Optimizer")
    st.sidebar.markdown("""
    **Multi-Page System**
    - 📥 **Page 1:** Upload & compute current metrics
    - ⚙️ **Page 2:** Generate optimized recommendations
    - 🕹️ **Page 3:** Simulation
    - 📊 **Page 4:** Comparison
    
    **Supported Models**
    - M/M/1 (single server)
    - M/M/c (multi-server)
    - M/G/1 (general service time)
    
    **Schema** (4 required + 1 optional)
    """)
    
    st.sidebar.markdown(f"""
    ```
    {', '.join(REQUIRED_COLUMNS)}
    variance (optional)
    ```
    """)
    
    # Status indicator
    st.sidebar.markdown("---")
    col1, col2, col3, col4 = st.sidebar.columns(4)
    
    with col1:
        status = "✅" if st.session_state.get("current_data") is not None else "⭕"
        st.metric("Page 1", status)
    
    with col2:
        status = "✅" if st.session_state.get("recommended_data") is not None else "⭕"
        st.metric("Page 2", status)
    
    with col3:
        status = "✅" if st.session_state.get("comparison_data") is not None else "⭕"
        st.metric("Page 3", status)
    
    with col4:
        status = "✅" if st.session_state.get("simulation_results") is not None else "⭕"
        st.metric("Page 4", status)


if __name__ == "__main__":
    main()
