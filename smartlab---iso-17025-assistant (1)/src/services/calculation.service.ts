
import { Injectable } from '@angular/core';
import { Parameter, Result, CalibrationSnapshot } from '../models';

@Injectable({ providedIn: 'root' })
export class CalculationService {

  mean(values: number[]): number {
    if (values.length === 0) return 0;
    return values.reduce((a, b) => a + b, 0) / values.length;
  }

  stdev(values: number[]): number {
    if (values.length < 2) return 0;
    const n = values.length;
    const m = this.mean(values);
    return Math.sqrt(values.map(x => Math.pow(x - m, 2)).reduce((a, b) => a + b) / (n - 1));
  }

  convertUnit(value: number, fromUnit: string, toUnit: string): number {
    if (value === null || value === undefined) return 0;
    if (!fromUnit || !toUnit) return value;
    
    const u1 = fromUnit.toLowerCase().trim();
    const u2 = toUnit.toLowerCase().trim();
    
    if (u1 === u2) return value;

    // Concentration: ppm <-> ppb
    if (u1 === 'ppm' && u2 === 'ppb') return value * 1000.0;
    if (u1 === 'ppb' && u2 === 'ppm') return value / 1000.0;

    // Mass Concentration: mg/m3 <-> ug/m3
    // We check for inclusion to handle variations like 'mg/m^3'
    if (u1.includes('mg') && u2.includes('ug')) return value * 1000.0;
    if (u1.includes('ug') && u2.includes('mg')) return value / 1000.0;

    // Temperature: C, K, F
    // C <-> K
    if (u1 === 'c' && u2 === 'k') return value + 273.15;
    if (u1 === 'k' && u2 === 'c') return value - 273.15;
    
    // C <-> F
    if (u1 === 'c' && u2 === 'f') return (value * 9/5) + 32;
    if (u1 === 'f' && u2 === 'c') return (value - 32) * 5/9;

    // K <-> F
    if (u1 === 'k' && u2 === 'f') return ((value - 273.15) * 9/5) + 32;
    if (u1 === 'f' && u2 === 'k') return ((value - 32) * 5/9) + 273.15;
    
    return value;
  }

  runAnalysis(
    projectName: string,
    parameter: Parameter,
    calibration: CalibrationSnapshot,
    readings: number[],
    inputUnit: string
  ): Omit<Result, 'id'> {
    
    // 1. Convert readings to the parameter's standard unit
    const convertedReadings = readings.map(r => this.convertUnit(r, inputUnit, parameter.unit));

    const n = convertedReadings.length;
    const mean = this.mean(convertedReadings);

    // Type A uncertainty (calculated on converted values)
    const uA = n > 1 ? (this.stdev(convertedReadings) / Math.sqrt(n)) : 0;

    // Type B uncertainty components (from Calibration)
    // Assuming calibration uncertainty is already in the parameter's standard unit
    const uCal = calibration.certUnc / (calibration.kFactor || 2.0);
    const uRes = calibration.resolution / Math.sqrt(3);
    const uDrift = calibration.drift / Math.sqrt(3);
    const uAcc = calibration.accuracy / Math.sqrt(3);

    // Combined uncertainty
    const uC = Math.sqrt(uA ** 2 + uCal ** 2 + uRes ** 2 + uDrift ** 2 + uAcc ** 2);
    
    // Expanded uncertainty (k=2 for ~95% confidence)
    const uExp = uC * 2.0;

    // Trust interval
    const minTrust = mean - uExp;
    const maxTrust = mean + uExp;
    
    // Status
    let status: 'PASS' | 'WARN' | 'FAIL' = 'PASS';
    if (parameter.critLimit && mean > parameter.critLimit) {
      status = 'FAIL';
    } else if (parameter.warnLimit && mean > parameter.warnLimit) {
      status = 'WARN';
    }

    return {
      project: projectName,
      param: parameter.name,
      mean, // The mean is stored in the STANDARD unit
      uExp,
      minTrust,
      maxTrust,
      status,
      timestamp: new Date().toISOString(),
      auditor: 'SmartLab User',
      readings, // Store original raw readings? Or converted? Usually raw is better for audit, but let's store raw.
      calibrationSnapshot: calibration,
    };
  }
}
