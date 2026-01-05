
# SmartLab Enterprise - ISO 17025 Assistant

**Version:** 0.6  
**Developer:** Eng. Mohammad Telfah  
**Repository:** [https://github.com/mhmdtelfah21/ISO-17025](https://github.com/mhmdtelfah21/ISO-17025)

SmartLab is a specialized web-based laboratory assistant designed to help Quality Managers and Technicians calculate measurement uncertainty according to **ISO 17025** standards.

## Features

- **Project Management:** Create, save, and load analysis projects for different sites or audits.
- **Metrology Data Management:** Manage global calibration profiles for devices (uncertainty, drift, resolution, etc.).
- **Measurement Analysis:** 
  - Grid-based data entry.
  - Automatic unit conversion (e.g., ppb to ppm, Celsius to Kelvin).
  - Specific calibration overrides per project.
- **Results Calculation:** 
  - Calculates Mean, Standard Deviation (Type A).
  - Combines Type B uncertainties (Certificate, Resolution, Drift, Accuracy).
  - Determines Expanded Uncertainty (k=2).
  - Pass/Warn/Fail status based on parameter limits.

## Tech Stack

- **Framework:** Angular (v18+) - Standalone Components, Signals, Zoneless.
- **Styling:** Tailwind CSS.
- **Language:** TypeScript.

## Getting Started

1. **Install Dependencies:**
   ```bash
   npm install
   ```

2. **Run Development Server:**
   ```bash
   ng serve
   ```
   Navigate to `http://localhost:4200/`.

## GitHub Setup

To push this existing project to your repository:

```bash
git init
git add .
git commit -m "Initial commit of SmartLab v0.6"
git branch -M main
git remote add origin https://github.com/mhmdtelfah21/ISO-17025.git
git push -u origin main
```

## License

Copyright © Eng. Mohammad Telfah.
