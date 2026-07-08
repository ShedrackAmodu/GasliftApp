# Gas Lift Opportunity Automation System - User Manual

This is the comprehensive user manual for the Gas Lift Opportunity Automation System web application.

## Table of Contents

1. [Introduction](#introduction)
2. [How the System Works](#how-the-system-works-overview)
3. [Accessing the System](#accessing-the-system)
4. [Step by Step User Guide](#step-by-step-user-guide)
5. [Understanding the Logic](#understanding-the-behind-the-scenes-logic)
6. [Troubleshooting Guide](#troubleshooting-guide)
7. [Frequently Asked Questions](#frequently-asked-questions-faq)
8. [Glossary](#glossary-plain-english)
9. [Next Steps](#next-steps-after-using-the-system)
10. [Contact & Support](#contact--support)

---

## Introduction

Welcome to the Gas Lift Opportunity Automation System – a smart web tool that helps you find which wells are good candidates for gas lift installation.

### What is Gas Lift?

Gas lift is a method used in oil production to help wells produce more oil. Think of it like adding a straw to a drink – it helps push the oil to the surface when the well's natural pressure isn't strong enough anymore.

### Why This System?

In many oilfields, engineers manually review hundreds of wells to decide which ones need gas lift. This is time consuming and can be inconsistent. This system automates that process – it analyses well test data, identifies wells with declining trends, and ranks them so you know exactly which wells to focus on.

### Who Is This Manual For?

This manual is designed for everyone – whether you're a petroleum engineer, a production technologist, a field operator, or a manager. We explain technical concepts in plain English, step by step.

---

## How the System Works (Overview)

Here's the simple flow of using the system:

| Step | What You Do | What the System Does |
|------|------------|----------------------|
| 1 | Upload well test data (Excel/CSV file) | Reads and stores your data |
| 2 | Map your columns to the system's required fields | Matches your data to our analysis requirements |
| 3 | Preview your data to check it's correct | Shows you a sample of what you uploaded |
| 4 | Adjust weighting sliders (optional) | Controls how much each parameter matters in ranking |
| 5 | View individual well trends | Shows you charts for each well's performance |
| 6 | Click "Run Analysis" | Calculates trends and ranks all wells |
| 7 | View the Results page | See ranked candidate wells with explanations |
| 8 | Export results (optional) | Download reports for sharing |

---

## Accessing the System

### Login

- Open your web browser and go to the system URL (provided by your administrator).
- Enter your username and password.
- Click Login.

### Dashboard

After login, you'll see the main dashboard. From here, you can navigate to:
- **Upload Data** – to start a new analysis
- **My Analyses** – to view previous analysis sessions
- **Results** – to see ranked candidates

---

## Step by Step User Guide

### Step 1: Upload Your Well Test Data

Click on "Upload Data" in the navigation menu.

#### File Requirements:

- **File format**: Excel (.xlsx) or CSV (.csv)
- **Size limit**: Up to 100 MB (contact your admin if you need larger files)

#### Required Columns (Must be present in your file):

Your well test data must contain these columns (the names don't have to match exactly – you'll map them in Step 2):

| Required Parameter | What It Measures | Example Column Names |
|-------------------|-----------------|----------------------|
| Well | Well name or ID | Well, WellName, Well_ID |
| Date | Test date | Date, TestDate, DateTime |
| BS&W (%) | Basic Sediment & Water – percentage of water in produced fluids | BS&W, BSW, WaterCut, WC% |
| Net Oil (bopd) | Oil production rate in barrels per day | NetOil, OilRate, Oil_bopd |
| Form.GLR (scf/bbl) | Gas to liquid ratio – amount of gas produced per barrel of liquid | GLR, GasLiquidRatio, FormGLR |
| Prod Method | How the well is currently producing (e.g., Natural, ESP, Gas Lift) | ProductionMethod, ProdMethod |
| Test Status | Whether the test is valid (e.g., Normal, Shut in, Invalid) | Status, TestStatus |
| Tubing Pressure (psi) | Pressure inside the production tubing | TubingPressure, THP, TP |
| Flow Line Pressure (psi) | Pressure in the flowline | FlowLinePressure, FLP, FP |
| Well Choke Size | Choke opening size (e.g., 12/64″, 24/64″) | ChokeSize, Choke, WellChoke |

#### How to Upload:

1. Click "Choose File" and select your file.
2. Click "Upload".
3. Wait for the confirmation message: "Upload successful!"

---

### Step 2: Map Your Columns

After uploading, the system shows the Column Mapping page. This is where you tell the system which column in your file corresponds to each required parameter.

#### How to Map:

- For each required parameter (e.g., "Well"), you'll see a dropdown menu.
- Select the column name from your file that matches.
- **Example**: If your file has a column called Well_Name, select Well_Name next to "Well".

#### Tips:

- The system will try to auto match columns based on common names – check that it's correct.
- If a column is missing, the system will highlight it in red – you must fix this before proceeding.
- Click "Save Mapping" when you're done.

---

### Step 3: Preview Your Data

Once columns are mapped, you can preview your uploaded data to make sure everything looks right.

- You'll see a table showing the first 50 rows of your data.
- Check for:
  - Correct dates (format should be YYYY-MM-DD or similar)
  - Numeric values in the right columns (no text in BSW, Oil, GLR, etc.)
  - No empty or obviously wrong values

If something looks wrong:
- Go back and check your column mapping.
- If the data itself is wrong, re-upload a corrected file.

---

### Step 4: Adjust Parameter Weights (Optional)

This is where you can influence the ranking. The system analyzes four key parameters:

- BS&W (water percentage)
- Oil Rate (oil production)
- GLR (gas liquid ratio)
- Tubing Pressure (pressure in the well)

#### What Are Weights?

Weights are like importance scores. A higher weight means that parameter has more influence on the final ranking.

| Weight | Meaning |
|--------|---------|
| 0 | This parameter is ignored – not considered at all |
| 0.5 | Somewhat important |
| 1.0 | Normally important (default) |
| 2.0 | Very important – double the influence |

#### Default Settings:

| Parameter | Default Weight | Why? |
|-----------|----------------|------|
| BS&W | 100 | Water increase is a key sign a well needs gas lift |
| Oil Rate | 100 | Declining oil is a primary concern |
| GLR | 100 | Helps distinguish between gas drive and liquid loading issues |
| Tubing Pressure | 50 | Less critical but useful for diagnosis |

#### How to Adjust:

- Use the sliders or type in a number (0 to 200).
- Higher number = more influence on the ranking.
- If you're unsure, leave them at the defaults – they're set based on standard engineering practice.

#### Why Would You Change Weights?

- If your field has a severe water problem, you might increase BS&W weight.
- If GLR is the main concern, increase GLR weight.
- If you want to ignore Tubing Pressure, set it to 0.

---

### Step 5: View Individual Well Trends (Optional)

Before running the full analysis, you can explore how each well is performing.

- Go to the "Well Trend Analysis" section.
- Select a well name from the dropdown.
- The system will display charts showing:
  - BS&W over time – is it going up?
  - Oil Rate over time – is it going down?
  - GLR over time – is it going down?
  - Tubing Pressure over time – is it stable?

#### What to Look For:

- **Increasing BS&W** → water is coming in, making fluids heavier → gas lift can help.
- **Decreasing Oil Rate** → production is dropping → gas lift might restore it.
- **Decreasing GLR** → not enough gas is coming from the reservoir → gas lift could provide that gas.
- **Stable/declining Tubing Pressure** – indicates the well might be struggling to lift fluids.

This step helps you understand your wells before the system automatically analyzes everything.

---

### Step 6: Run the Analysis

When you're ready:

1. Click the "Run Analysis" button at the top of the Template page.
2. A progress bar will appear – the system is:
   - Checking data quality
   - Calculating trends for each well (using statistical methods)
   - Applying your weights
   - Ranking all wells
3. When complete, you'll see: "Analysis complete! View Results."

---

### Step 7: View the Results

Click "View Results" or navigate to the Results page.

#### What You See:

| Column | What It Means |
|--------|---------------|
| Well | Well name |
| UID | Unique identifier for the well |
| BSW_Flag | Yes = BSW is trending upward (bad), No = no significant trend |
| OilRate_Flag | Yes = Oil rate is trending downward (bad), No = no significant trend |
| GLR_Flag | Yes = GLR is trending downward (bad), No = no significant trend |
| Rank | Ranking from 1 (best candidate) down to the lowest |
| Summary_Comment | A plain English explanation of why the well is (or isn't) a candidate |

#### Understanding the Summary Comments:

| Example Comment | What It Means |
|-----------------|---------------|
| "BSW is moderately trending up and oil rate is aggressively declining." | This well has a clear water increase and oil drop – strong candidate. |
| "Does not show clear adverse production or fluid trends." | This well is stable – not a priority for gas lift. |

#### The Flags in Plain Terms:

- **BSW_Flag = Yes** → Water is increasing. More water means heavier fluid – gas lift can help push it out.
- **OilRate_Flag = Yes** → Oil production is falling. Gas lift can boost it back up.
- **GLR_Flag = Yes** → The well's natural gas supply is dropping. Gas lift can supplement that gas.

---

### Step 8: Export Results (Optional)

You can download your results for reporting or further analysis:

- Click the "Export to Excel" button.
- A file named GasLift_Candidates.xlsx will download.
- This file contains the same table you see on the Results page.

You can also:
- Print the results directly from your browser.
- Share the page link with colleagues (they'll need login access).

---

## Understanding the "Behind the Scenes" Logic

(For those who want to know how the system makes decisions)

The system doesn't just look at the latest test – it looks at trends over time. It uses two statistical tools:

### A) Mann Kendall Trend Test

- **Plain English**: This test asks: "Is there a real, consistent upward or downward pattern in this data, or is it just random noise?"
- **The result is**: Upward trend, Downward trend, or No significant trend.

### B) Sen's Slope Estimator

- **Plain English**: If there is a trend, how fast is it changing? (e.g., "BSW is increasing by 0.5% per month").
- **This gives us the magnitude of the trend** (mild, moderate, or aggressive).

### How the Ranking Works:

1. The system calculates a "trend score" = (trend direction) × (magnitude) for each parameter.
2. It multiplies each score by your weight for that parameter.
3. It adds all scores together to get a total Candidate Score.
4. Higher score = higher rank (1, 2, 3...).

### What the Adjective Descriptors Mean:

| Descriptor | Meaning |
|-----------|---------|
| Slightly | The trend exists but is mild – changes are small over time. |
| Moderately | The trend is clear and noticeable – moderate change rate. |
| Aggressively | The trend is strong and fast – urgent attention needed. |

---

## Troubleshooting Guide

### Problem: "Upload failed – File format not supported"

**Solution**: Make sure your file is .xlsx or .csv. If it's an older .xls format, open it in Excel and save as .xlsx.

### Problem: "Column mapping error – Required column not found"

**Solution**:
- Check that your file actually has all 10 required columns.
- Column names don't have to match exactly, but you must select the correct match in the dropdown.
- If a column is truly missing, you need to add it to your data file.

### Problem: "No wells found – data is empty"

**Solution**:
- Check that your data has more than just a header row.
- Ensure you haven't filtered or hidden rows in your Excel file before uploading.

### Problem: Analysis runs but no wells are ranked (all flags = No)

**Possible reasons**:
- Your wells are all stable – no significant trends. Congratulations, you don't need gas lift! But you can still review them.
- Your data window is too short (needs at least 5-10 data points per well).
- Check if you have recent test data – old data might mask current trends.

### Problem: "Date format error – dates not recognized"

**Solution**:
- The system expects standard date formats like 2024-01-15 or 01/15/2024.
- If your dates are in a custom format, open the file in Excel, format the Date column as "Date" and save again.

### Problem: Results show "0" for all ranks

**Solution**:
- Your weights might be set to zero for all parameters – go back and set at least one weight > 0.
- Alternatively, check that your data has the correct numeric values (no text in numeric columns).

### Problem: The system is slow

**Solution**:
- If you have more than 10,000 rows, consider reducing your dataset (e.g., last 2 years only).
- Close other browser tabs to free up memory.

---

## Frequently Asked Questions (FAQ)

**Q: Do I need to be a statistician to use this?**
A: Absolutely not. The system does all the math for you. Just upload data, map columns, and press "Run".

**Q: Can I trust the system's recommendations?**
A: Yes – the system follows the same logic that experienced engineers use. However, the final decision should always involve human judgment. Think of this as your assistant, not your replacement.

**Q: What if my field doesn't use Gas Lift yet?**
A: The system helps you identify wells where Gas Lift would be beneficial – even if you're starting from scratch. It's a screening tool.

**Q: Can I analyze multiple fields at once?**
A: Yes, as long as your data file includes all wells from different fields, the system will analyze all of them and rank them together. You can also filter by field in the results page.

**Q: What does "Form.GLR" mean?**
A: Formation Gas Liquid Ratio – it's the amount of gas that comes out of the reservoir with each barrel of liquid. A declining GLR means the reservoir is running out of natural gas, which is a sign that artificial gas lift could help.

**Q: How often should I run the analysis?**
A: We recommend running it whenever you have new well test data (e.g., monthly, quarterly). This helps you stay on top of declining wells.

**Q: Can I run the system on my phone or tablet?**
A: Yes, the web application is mobile friendly. However, for data upload and detailed viewing, a desktop/laptop is easier.

**Q: Is my data safe?**
A: Yes – all data is encrypted and stored securely. Only you and authorized administrators can access your analyses.

---

## Glossary (Plain English)

| Term | Plain English Definition |
|------|------------------------|
| BS&W | Basic Sediment & Water – the percentage of water mixed with the oil. Higher = more water. |
| bopd | Barrels of Oil Per Day – how much oil is produced each day. |
| scf/bbl | Standard Cubic Feet per Barrel – how much gas comes with each barrel of fluid. |
| GLR | Gas Liquid Ratio – same as above. |
| Tubing Pressure | The pressure inside the pipe that brings oil up. Lower pressure can mean the well is struggling. |
| Flow Line Pressure | The pressure in the pipe that carries oil to the processing facility. |
| Choke | A valve that restricts flow. If it's too small, it can falsely look like production is declining. |
| Trend | A consistent pattern over time – up, down, or flat. |
| Candidate | A well that might benefit from gas lift. |
| Rank | Your well's position in the list – #1 is the most urgent candidate. |
| Weight | How much importance we give to a parameter in the ranking. |
| Sen's Slope | A fancy name for the "rate of change" – how fast something is increasing or decreasing. |
| Mann Kendall Test | A statistical test that checks if a trend is real or just random. |

---

## Next Steps After Using the System

Once you have your ranked list of candidates:

1. Review the top 5-10 wells – these are your highest priority.
2. Double check with field data – visit the well site if possible, or check recent reports.
3. Build a detailed well model (e.g., using PROSPER) for the top candidates to confirm gas lift benefits.
4. Create a workover/intervention plan – schedule the gas lift installation.
5. Monitor results – after gas lift is installed, run the analysis again to see improvement.

---

## Contact & Support

- **System Administrator**: [Name/Email]
- **Technical Support**: [Helpdesk link or email]
- **Feedback**: We welcome your suggestions – please use the feedback form in the system.

---

Thank you for using the Gas Lift Opportunity Automation System!

We hope this tool saves you time, helps you make better decisions, and boosts your production.

© 2026 – Gas Lift Automation Project
