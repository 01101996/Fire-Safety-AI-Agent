import streamlit as st
import pandas as pd
import math
from datetime import date
from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak

st.set_page_config(page_title="FireSafe AI | Pakistan", page_icon="🔥", layout="wide")

# -----------------------------
# DATA
# -----------------------------
COSTS = {
    "ABC 6kg extinguisher": (8500, 12000, "each"),
    "CO2 5kg extinguisher": (16000, 22000, "each"),
    "Fire blanket": (2500, 3000, "each"),
    "Smoke/heat detector": (2500, 6000, "each"),
    "Manual call point": (1300, 4500, "each"),
    "Fire alarm panel + basic accessories": (25000, 150000, "lot"),
    "Exit sign / emergency light": (3000, 8000, "each"),
    "Fire door": (45000, 120000, "each"),
    "Fire hose reel / cabinet": (25000, 60000, "each"),
    "Hydrant / landing valve point": (30000, 80000, "each"),
    "Fire pump package": (500000, 1800000, "lot"),
    "Fire water tank": (250000, 1000000, "lot"),
    "Sprinkler system": (1500, 4000, "per m2"),
    "Fire alarm installation allowance": (150000, 500000, "lot"),
    "Emergency response plan / signage package": (25000, 100000, "lot"),
}

RULES = [
    {"id":"FS-01","topic":"Occupancy / hazard classification","standard":"BCP Fire Safety Provisions 2016 + NFPA 101 / NFPA 1",
     "requirement":"Occupancy classification and hazard level must be established before selecting protection systems.",
     "logic":"always","priority":"Critical"},
    {"id":"FS-02","topic":"Portable fire extinguishers","standard":"NFPA 10-2026",
     "requirement":"Provide portable extinguishers appropriate to hazards, rating, placement and accessibility; final quantity/spacing must be verified from the adopted NFPA 10 tables.",
     "logic":"always","priority":"High"},
    {"id":"FS-03","topic":"Fire alarm / detection","standard":"BCP Fire Safety Provisions 2016 + NFPA 72",
     "requirement":"Provide detection/alarm where required by occupancy, building characteristics and AHJ; design, installation, testing and maintenance should follow the adopted NFPA 72 edition.",
     "logic":"alarm","priority":"Critical"},
    {"id":"FS-04","topic":"Means of egress","standard":"BCP Fire Safety Provisions 2016 + NFPA 101",
     "requirement":"Provide compliant exits, exit access, discharge, travel paths, exit signs and emergency lighting as applicable.",
     "logic":"egress","priority":"Critical"},
    {"id":"FS-05","topic":"Automatic sprinklers","standard":"NFPA 13 + BCP Fire Safety Provisions 2016",
     "requirement":"Where sprinklers are required, provide a hydraulically designed system using the adopted NFPA 13 edition and applicable occupancy/hazard criteria.",
     "logic":"sprinkler","priority":"Critical"},
    {"id":"FS-06","topic":"Standpipe / hydrant","standard":"BCP Fire Safety Provisions 2016 + NFPA 14",
     "requirement":"Where required, provide standpipe/hydrant protection with approved water supply, hose connections and fire department access.",
     "logic":"hydrant","priority":"Critical"},
    {"id":"FS-07","topic":"Fire pump / water supply","standard":"NFPA 20 / NFPA 22 + BCP",
     "requirement":"Where water-based systems require a dedicated fire pump or tank, size and hydraulically verify the system; do not rely on a generic cost estimate as a design.",
     "logic":"water","priority":"Critical"},
    {"id":"FS-08","topic":"Emergency lighting and exit signs","standard":"BCP Fire Safety Provisions 2016 + NFPA 101",
     "requirement":"Provide emergency lighting and exit identification along required egress routes.",
     "logic":"always","priority":"High"},
    {"id":"FS-09","topic":"Emergency response plan and drills","standard":"BCP Fire Safety Provisions 2016",
     "requirement":"Maintain an emergency response plan, emergency contacts, evacuation arrangements, fire drills and training records as applicable.",
     "logic":"always","priority":"High"},
    {"id":"FS-10","topic":"Electrical fire prevention","standard":"BCP Fire Safety Provisions 2016 + applicable electrical code",
     "requirement":"Control overloaded circuits, damaged cables, poor connections and combustible storage near electrical equipment; maintain safe access to panels.",
     "logic":"always","priority":"High"},
    {"id":"FS-11","topic":"Fire doors / compartmentation","standard":"BCP Fire Safety Provisions 2016 + NFPA 101",
     "requirement":"Provide rated doors, protected openings and compartmentation where required by occupancy, construction and egress strategy.",
     "logic":"compartment","priority":"High"},
    {"id":"FS-12","topic":"Commercial kitchen protection","standard":"NFPA 96 + BCP / AHJ requirements",
     "requirement":"Commercial cooking operations may require listed hood/exhaust protection, automatic suppression, shutdown/interlocks and appropriate extinguishers.",
     "logic":"kitchen","priority":"Critical"},
]

# -----------------------------
# HELPERS
# -----------------------------
def money(v):
    return f"PKR {v:,.0f}"

def add_cost(items, name, qty, note=""):
    if qty <= 0:
        return
    lo, hi, unit = COSTS[name]
    if unit == "per m2":
        low = lo * qty
        high = hi * qty
        qty_text = f"{qty:,.0f} m²"
    else:
        low = lo * qty
        high = hi * qty
        qty_text = f"{qty:,.0f}"
    items.append({"Item":name, "Qty":qty_text, "Unit":unit, "Low PKR":low, "High PKR":high, "Basis":note})

def build_assessment(d):
    findings = []
    cost_items = []

    area = d["floor_area"] * d["floors"]
    occupants = d["occupants"]
    commercial = d["occupancy"] in ["Office","Retail","Assembly","Hotel","Hospital","Educational","Industrial","Warehouse"]
    highrise = d["high_rise"]
    multi = d["floors"] > 1

    # Extinguishers: screening quantity only
    # Conservative planning allowance; final spacing/rating is an NFPA 10 verification step.
    abc_qty = max(1, math.ceil(area / 500))
    co2_qty = max(1, math.ceil(d["electrical_rooms"] / 1)) if d["electrical_rooms"] > 0 else 0
    add_cost(cost_items, "ABC 6kg extinguisher", abc_qty, "Screening allowance: 1 per ~500 m²; verify NFPA 10 hazard/rating/travel-distance tables.")
    if co2_qty:
        add_cost(cost_items, "CO2 5kg extinguisher", co2_qty, "One planning allowance per electrical/IT room; verify hazard and local requirements.")

    alarm_req = commercial or occupants > 50 or multi or d["sleeping_occupancy"] or d["high_hazard"]
    sprinkler_req = highrise or d["high_hazard"] or d["sprinkler_required"] or d["warehouse_storage"] or d["sleeping_occupancy"]
    hydrant_req = highrise or d["floors"] >= 3 or d["building_area"] >= 5000 or d["hydrant_required"]
    water_req = sprinkler_req or hydrant_req

    if alarm_req:
        detector_qty = max(1, math.ceil(area / 60))
        mcp_qty = max(1, math.ceil(area / 500))
        add_cost(cost_items, "Smoke/heat detector", detector_qty, "Planning allowance only; final spacing/type/location requires NFPA 72 design.")
        add_cost(cost_items, "Manual call point", mcp_qty, "Planning allowance only; final locations require adopted design/AHJ review.")
        add_cost(cost_items, "Fire alarm panel + basic accessories", 1, "Indicative small-to-medium system allowance.")
        add_cost(cost_items, "Fire alarm installation allowance", 1, "Indicative allowance; contractor BOQ required.")

    if d["exit_signs_required"]:
        exit_qty = max(2, d["floors"] * 2)
        add_cost(cost_items, "Exit sign / emergency light", exit_qty, "Planning allowance; final count/layout based on egress and photometric design.")

    if sprinkler_req:
        add_cost(cost_items, "Sprinkler system", area, "Indicative installed allowance per m²; hydraulic design and hazard classification required.")

    if hydrant_req:
        points = max(2, d["floors"] * 2)
        add_cost(cost_items, "Hydrant / landing valve point", points, "Planning allowance; final network/hydrant spacing requires approved design.")
        add_cost(cost_items, "Fire hose reel / cabinet", points, "Planning allowance; verify required system and coverage.")

    if water_req:
        add_cost(cost_items, "Fire pump package", 1, "Indicative only; pump duty must be hydraulically calculated.")
        add_cost(cost_items, "Fire water tank", 1, "Indicative only; required capacity/duration must be calculated.")

    if d["rated_doors_required"]:
        add_cost(cost_items, "Fire door", max(2, d["floors"] * 2), "Planning allowance; rating, hardware and locations require code review.")

    if d["kitchen"]:
        add_cost(cost_items, "Fire blanket", 2, "Planning allowance for cooking area.")
        findings.append(["FS-12","Commercial kitchen protection","REVIEW","NFPA 96 / AHJ requirements should be checked for hood, duct, suppression and fuel/electrical shutdown.","Critical"])

    # Core findings
    findings += [
        ["FS-01","Occupancy / hazard classification","REVIEW",
         f"Occupancy entered as {d['occupancy']}; confirm exact code classification and hazard level before final design.","Critical"],
        ["FS-02","Portable fire extinguishers","REVIEW",
         f"Planning allowance generated: {abc_qty} ABC units" + (f" + {co2_qty} CO₂ units for electrical/IT rooms." if co2_qty else ".") +
         " Final number, ratings, travel distance and mounting must be verified against adopted NFPA 10.","High"],
        ["FS-03","Fire alarm / detection", "REQUIRED" if alarm_req else "REVIEW",
         "Alarm/detection is triggered by the screening logic. Confirm exact applicability and device spacing under BCP/NFPA 72/AHJ.", "Critical"],
        ["FS-04","Means of egress","REVIEW",
         f"Inputs: {d['floors']} floor(s), {occupants} occupants, {d['exit_stairs']} exit stair(s), {d['exit_doors']} exit door(s). Verify occupant load, exit capacity, travel distance, common path, discharge and door swing.","Critical"],
        ["FS-05","Automatic sprinklers","REQUIRED" if sprinkler_req else "REVIEW",
         "Screening logic indicates sprinkler review is necessary." if sprinkler_req else "No sprinkler trigger selected by screening inputs; verify occupancy, area, height, storage and AHJ requirements.","Critical"],
        ["FS-06","Standpipe / hydrant","REQUIRED" if hydrant_req else "REVIEW",
         "Screening logic indicates hydrant/standpipe review is necessary." if hydrant_req else "Confirm whether local fire authority/building provisions require hydrant/standpipe protection.","Critical"],
        ["FS-07","Fire pump / water supply","REQUIRED" if water_req else "REVIEW",
         "Water-based fire protection is triggered; hydraulic calculations and water-supply verification are mandatory.","Critical"],
        ["FS-08","Emergency lighting and exit signs","REQUIRED" if d["exit_signs_required"] else "REVIEW",
         "Provide/verify emergency lighting and exit identification along required egress paths.","High"],
        ["FS-09","Emergency response plan and drills","REQUIRED",
         "Maintain ERP, evacuation plan, emergency contacts, wardens, training and drill records.","High"],
        ["FS-10","Electrical fire prevention","REQUIRED",
         "Inspect electrical distribution, cables, panels, clearances, earthing/bonding and combustible storage controls.","High"],
        ["FS-11","Fire doors / compartmentation","REQUIRED" if d["rated_doors_required"] else "REVIEW",
         "Verify rated doors, protected openings and compartmentation where required by the adopted code strategy.","High"],
    ]
    return findings, pd.DataFrame(cost_items)

def make_pdf(d, findings, costs):
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=28,leftMargin=28,topMargin=28,bottomMargin=28)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="TitleCenter", parent=styles["Title"], alignment=TA_CENTER, fontSize=18))
    story = [Paragraph("FireSafe AI — Preliminary Fire Safety Assessment", styles["TitleCenter"]),
             Paragraph(f"Generated: {date.today().isoformat()}", styles["Normal"]), Spacer(1,8)]
    summary = [
        ["Parameter","Value"],
        ["Occupancy", d["occupancy"]],
        ["Floors", str(d["floors"])],
        ["Floor area", f"{d['floor_area']:,.0f} m²"],
        ["Total gross area (input × floors)", f"{d['floor_area']*d['floors']:,.0f} m²"],
        ["Occupants", str(d["occupants"])],
        ["High-rise flag", "Yes" if d["high_rise"] else "No"],
    ]
    t = Table(summary, colWidths=[210,280]); t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.lightgrey),("GRID",(0,0),(-1,-1),0.4,colors.grey),("VALIGN",(0,0),(-1,-1),"TOP")]))
    story += [t, Spacer(1,12), Paragraph("Findings", styles["Heading2"])]
    fdata = [["ID","Topic","Status","Finding","Priority"]] + [list(x) for x in findings]
    ft = Table(fdata, repeatRows=1, colWidths=[35,90,55,255,55])
    ft.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.lightgrey),("GRID",(0,0),(-1,-1),0.3,colors.grey),("FONTSIZE",(0,0),(-1,-1),7),("VALIGN",(0,0),(-1,-1),"TOP")]))
    story += [ft, PageBreak(), Paragraph("Indicative Cost Plan", styles["Heading2"])]
    if len(costs):
        cdata = [["Item","Qty","Unit","Low PKR","High PKR","Basis"]]
        for _,r in costs.iterrows():
            cdata.append([r["Item"],r["Qty"],r["Unit"],money(r["Low PKR"]),money(r["High PKR"]),r["Basis"]])
        ct = Table(cdata, repeatRows=1, colWidths=[105,45,45,65,65,165])
        ct.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.lightgrey),("GRID",(0,0),(-1,-1),0.3,colors.grey),("FONTSIZE",(0,0),(-1,-1),7),("VALIGN",(0,0),(-1,-1),"TOP")]))
        story.append(ct)
        low, high = costs["Low PKR"].sum(), costs["High PKR"].sum()
        story += [Spacer(1,8), Paragraph(f"<b>Indicative total range: {money(low)} – {money(high)}</b>", styles["Normal"])]
    story += [Spacer(1,16), Paragraph("Important: This is a preliminary screening and budgeting tool, not a stamped fire protection design or AHJ approval. Exact NFPA clauses, editions, calculations, equipment listings, hydraulic design, occupant-load calculations, egress capacity and local requirements must be verified by a competent fire protection professional/AHJ.", styles["Normal"])]
    doc.build(story)
    return buf.getvalue()

# -----------------------------
# UI
# -----------------------------
st.title("🔥 FireSafe AI — Building / Workplace Fire Safety Agent")
st.caption("Preliminary code-screening + gap assessment + Pakistan-market budgeting")

with st.sidebar:
    st.header("Project")
    project = st.text_input("Project / Building name", "Sample Office Building")
    location = st.text_input("City / Province", "Peshawar, Khyber Pakhtunkhwa")
    st.divider()
    st.subheader("Adopted standards")
    bcp = st.text_input("Pakistan code", "Building Code of Pakistan — Fire Safety Provisions 2016")
    nfpa_edition = st.selectbox("NFPA assessment baseline", ["NFPA current edition — verify adopted edition","NFPA 2026/2025 baseline","NFPA 2021 baseline"])
    st.info("Always verify the edition adopted by the AHJ/project contract.")

c1,c2,c3 = st.columns(3)
with c1:
    occupancy = st.selectbox("Occupancy", ["Office","Retail","Assembly","Hotel","Hospital","Educational","Industrial","Warehouse","Residential","Other"])
    floors = st.number_input("Number of floors", min_value=1, max_value=100, value=2)
    floor_area = st.number_input("Approx. floor area (m²)", min_value=20.0, value=1000.0, step=50.0)
    occupants = st.number_input("Maximum occupants", min_value=1, value=80)
with c2:
    building_height = st.number_input("Building height (m)", min_value=1.0, value=10.0, step=0.5)
    high_rise = st.checkbox("Treat as high-rise / high-height building", value=False)
    sleeping_occupancy = st.checkbox("Sleeping / residential care occupancy", value=False)
    high_hazard = st.checkbox("High-hazard process / storage", value=False)
    warehouse_storage = st.checkbox("Warehouse / high-piled storage", value=False)
with c3:
    exit_stairs = st.number_input("Exit stairs / protected stairs", min_value=0, value=2)
    exit_doors = st.number_input("Exit doors / exit discharge doors", min_value=0, value=2)
    electrical_rooms = st.number_input("Electrical / IT rooms", min_value=0, value=1)
    kitchen = st.checkbox("Commercial kitchen", value=False)

st.subheader("Protection / existing-condition inputs")
x1,x2,x3 = st.columns(3)
with x1:
    sprinkler_required = st.checkbox("Sprinkler system required / specified", value=False)
    hydrant_required = st.checkbox("Hydrant / standpipe required / specified", value=False)
with x2:
    exit_signs_required = st.checkbox("Emergency lighting & exit signs required", value=True)
    rated_doors_required = st.checkbox("Rated fire doors / compartmentation required", value=True)
with x3:
    st.write("Use these switches for known project/AHJ requirements.")
    st.warning("Do not use a false/true switch as a substitute for code analysis.")

if st.button("🚒 Run Fire Safety Assessment", type="primary", use_container_width=True):
    d = dict(project=project, location=location, occupancy=occupancy, floors=floors,
             floor_area=floor_area, occupants=occupants, building_height=building_height,
             high_rise=high_rise, sleeping_occupancy=sleeping_occupancy, high_hazard=high_hazard,
             warehouse_storage=warehouse_storage, exit_stairs=exit_stairs, exit_doors=exit_doors,
             electrical_rooms=electrical_rooms, kitchen=kitchen, sprinkler_required=sprinkler_required,
             hydrant_required=hydrant_required, exit_signs_required=exit_signs_required,
             rated_doors_required=rated_doors_required)
    findings, costs = build_assessment(d)

    total_low = costs["Low PKR"].sum() if len(costs) else 0
    total_high = costs["High PKR"].sum() if len(costs) else 0
    required = sum(1 for x in findings if x[2] == "REQUIRED")
    review = sum(1 for x in findings if x[2] == "REVIEW")

    a,b,c,dcol = st.columns(4)
    a.metric("Requirements triggered", required)
    b.metric("Review items", review)
    c.metric("Budget low", money(total_low))
    dcol.metric("Budget high", money(total_high))

    st.subheader("Assessment findings")
    fdf = pd.DataFrame(findings, columns=["ID","Topic","Status","Finding","Priority"])
    st.dataframe(fdf, use_container_width=True, hide_index=True)

    st.subheader("Indicative Pakistan-market cost plan")
    if len(costs):
        display = costs.copy()
        display["Low PKR"] = display["Low PKR"].map(money)
        display["High PKR"] = display["High PKR"].map(money)
        st.dataframe(display, use_container_width=True, hide_index=True)
        st.caption("Market ranges are indicative budgeting values, not contractor quotations. Obtain current BOQs/quotations before procurement.")
    else:
        st.info("No cost items were generated from the selected screening inputs.")

    pdf = make_pdf(d, findings, costs)
    st.download_button("📄 Download PDF assessment", data=pdf, file_name="fire_safety_assessment.pdf", mime="application/pdf")

    csv = fdf.to_csv(index=False).encode()
    st.download_button("📊 Download findings CSV", data=csv, file_name="fire_safety_findings.csv", mime="text/csv")

    if len(costs):
        cost_csv = costs.to_csv(index=False).encode()
        st.download_button("💰 Download cost plan CSV", data=cost_csv, file_name="fire_safety_cost_plan.csv", mime="text/csv")

st.divider()
st.markdown("**Reference framework:** BCP Fire Safety Provisions 2016; NFPA 10 (portable extinguishers), NFPA 13 (sprinklers), NFPA 14 (standpipes), NFPA 20 (fire pumps), NFPA 22 (water tanks), NFPA 72 (fire alarm/signaling), NFPA 96 (commercial cooking), NFPA 101 (life safety).")
st.caption("This MVP intentionally avoids reproducing copyrighted NFPA text. Use licensed NFPA publications and the adopted local code/AHJ requirements for final engineering decisions.")
