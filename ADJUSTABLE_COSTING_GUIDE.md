# 🎚️ Adjustable Costing Parameters Guide

## ✅ Feature Added: Full Control Over All Costing Numbers

You can now **adjust ALL costing parameters** directly in the Streamlit dashboard in real-time.

---

## 📍 Where to Adjust Costs

### **Option 1: Sidebar (Global Settings)**
🔗 **Left sidebar** → **"💰 Costing Parameters"** section

- **💼 Cost per Cashier (₱/hr)** — Default: ₱87
- **⏳ Cost of Customer Wait (₱/hr)** — Default: ₱100
- **❌ Cost per Abandonment (₱)** — Default: ₱60

✨ **These settings persist** across all pages and optimize immediately when changed.

---

### **Option 2: Page 2 Optimization Settings (Quick Adjust)**
🔗 **Page 2** → **"⚙️ Configuration & Costing"** → **"Costing Settings" tab**

Same three parameters with detailed descriptions and real-time preview.

---

## 🔄 How Changes Work

1. **Adjust sidebar parameters** (or Page 2 settings)
2. **Values auto-save** to session state (immediately)
3. **Go to Page 2** → Click **"🚀 Run Optimization"**
4. **Cost analysis** uses **your new numbers**
5. **Page 3 comparison** shows savings **with new costing**

---

## 📊 Parameter Meanings

| Parameter | Code | Default | Range | Meaning |
|-----------|------|---------|-------|---------|
| **Cost per Cashier** | Cₛ | ₱87/hr | ₱10–₱500/hr | How much you pay per hour per server |
| **Cost of Wait** | Cw | ₱100/hr | ₱10–₱500/hr | How much customers value their time per hour |
| **Cost per Abandon** | Ca | ₱60 | ₱10–₱500 | Lost sale when customer leaves (avg basket) |

---

## 🧪 Try These Scenarios

### **Scenario 1: Lower Cashier Cost (₱50/hr)**
```
Sidebar: Change "Cost per Cashier" to 50.0
→ Fewer servers recommended
→ Higher wait times but lower staff cost
→ Different optimization vs ₱87 baseline
```

### **Scenario 2: High Customer Value (₱150/hr)**
```
Sidebar: Change "Cost of Customer Wait" to 150.0
→ MORE servers recommended (wait cost very high)
→ Willing to pay more staff to reduce wait
→ Significant daily savings from shorter queues
```

### **Scenario 3: Premium Abandonment (₱100)**
```
Sidebar: Change "Cost per Abandon" to 100.0
→ Higher penalty for lost customers
→ Optimization prioritizes service quality
→ Higher recommended server count
```

### **Scenario 4: Budget Scenario (All Low)**
```
Change ALL to minimum reasonable:
- Cₛ = 60.0 (contract workers)
- Cw = 50.0 (low-value customers)  
- Ca = 30.0 (low-basket customers)
→ Minimal staff, accept longer waits
→ Lowest cost option
```

---

## 💡 Real-Time Adjustment Workflow

```
1. Open Sidebar → "💰 Costing Parameters"
   
2. Move sliders:
   - Cashier: 87 → 100 (higher pay)
   - Wait Cost: 100 → 120 (customers more valuable)
   - Abandon: 60 → 80 (losing more per abandoned customer)
   
3. See summary update immediately:
   "Cₛ (Cashier): ₱100/hr"
   "Cw (Wait): ₱120/hr"
   "Ca (Abandon): ₱80"
   
4. Go to Page 2 → Click "🚀 Run Optimization"
   
5. Scroll to "💰 Cost Analysis"
   → Your NEW costs are calculated
   → See daily/monthly/annual savings with NEW parameters
   
6. Go to Page 3 → See comparison with NEW costing
```

---

## 🎯 Use Cases

### **Use Case 1: A/B Testing Staffing Models**
```
Test A: Cₛ = 87 (current reality) → Run optimization → Note results
         (Ctrl+A, change slider to 87)
         
Test B: Cₛ = 110 (higher pay contractors) → Run optimization → Compare
         (Change slider to 110, Page 2 "Run Optimization")
         
Conclusion: Which pays better overall?
```

### **Use Case 2: Sensitivity Analysis**
```
Question: How sensitive is optimization to customer wait value?

Cw = 50 (low value) → See recommendations
Cw = 100 (medium) → See recommendations
Cw = 150 (high) → See recommendations

Observe: Does server count change? By how much?
```

### **Use Case 3: Budget Planning**
```
"We can only afford 3 servers max"
→ Set Cₛ = cashier hourly cost
→ Adjust Cw/Ca until optimization recommends ≤3 servers
→ That's your costing threshold
```

---

## ⚙️ Technical Notes

### **Where Changes Are Stored**
- **Session State Keys:**
  - `st.session_state["cost_per_server_hr"]` (currently displayed value)
  - `st.session_state["cost_per_wait_hr"]`
  - `st.session_state["cost_per_abandonment"]`

- **Persistence:** Values persist for the current app session
- **Reset:** Refresh browser → Defaults to ₱87, ₱100, ₱60

### **Cost Calculation Formula**

For each time interval:
```
Total Cost = (Servers × Cₛ × hours) + (Wq × λ × Cw) + (λ × 0.10 × Ca)

Where:
  Servers = number of cashiers
  Cₛ = cost per server/hr (YOUR value from slider)
  hours = duration of interval (typically 1.0)
  Wq = average wait time (calculated by M/M/c)
  λ = arrival rate (customers/hr)
  Cw = cost per hour of wait (YOUR value from slider)
  Ca = cost per abandonment (YOUR value from slider)
```

### **Optimization Impact**

When you change costing parameters:
1. ✅ Recommended server count can **change** (Page 2)
2. ✅ Total cost breakdown **changes** (Page 2 & 3)
3. ✅ Daily/monthly savings **change** (Page 2 & 3)
4. ✅ Cost comparison **changes** (Page 3)
5. ❌ Queue metrics (Lq, Wq, Ls, Ws) **do NOT change** (they're physics-based)

---

## 🔗 Navigation

- 🔄 **Sidebar:** Left panel, always visible, global settings
- 📄 **Page 2 Costing Tab:** Quick local adjustments before optimization
- 💰 **Cost Analysis Sections:** Pages 2 & 3 show results with your latest costing
- 📋 **Export:** All costs included in comparison export (CSV)

---

## ✨ Features

✅ **Real-time updates** — Change value → immediately persists  
✅ **Input validation** — Range ₱10–₱500 enforced  
✅ **Dual location** — Sidebar (global) + Page 2 (quick preview)  
✅ **Visual feedback** — Metrics show current values  
✅ **Full integration** — All calculations use latest values  
✅ **No page reload needed** — Settings flow to all pages instantly  

---

## 📝 Citation Reference

Default values are based on:
```
Cₛ = ₱87/hr — flat cashier wage, no benefits included
Cw = ₱100/hr — estimated opportunity cost of a grocery customer's time, 
               approximated above the NCR 2026 minimum wage of ₱695/day ÷ 8hrs = ₱86.88/hr
Ca = ₱60/customer — based on 10% abandonment rate applied to an average 
                     grocery basket of ₱600/visit (NCR 2026 grocery standard)
```

Feel free to adjust these based on your **actual business data**.

---

## 🚀 Quick Start

1. Open dashboard: **http://localhost:8502**
2. Left sidebar → Find **"💰 Costing Parameters"**
3. Adjust any of the 3 sliders
4. Go to **Page 2** → Click **"🚀 Run Optimization"**
5. Scroll down → See "💰 Cost Analysis" with YOUR costs
6. See daily/monthly/annual savings
7. Try different values → Compare recommendations

---

**All costing numbers are now under YOUR control! 🎚️**
