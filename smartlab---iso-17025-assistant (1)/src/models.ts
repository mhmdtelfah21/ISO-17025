
export interface Parameter {
  id: number;
  name: string;
  unit: string;
  warnLimit: number;
  critLimit: number;
}

export interface Calibration {
  id: number;
  paramId: number;
  device: string;
  serial: string;
  date: string;
  certUnc: number;
  kFactor: number;
  resolution: number;
  drift: number;
  accuracy: number;
  active: boolean;
}

export interface CalibrationSnapshot {
  device: string;
  serial: string;
  certUnc: number;
  kFactor: number;
  resolution: number;
  drift: number;
  accuracy: number;
  source: 'GLOBAL' | 'HISTORY' | 'CUSTOM';
}

export interface Result {
  id: number;
  project: string;
  param: string;
  mean: number;
  uExp: number;
  minTrust: number;
  maxTrust: number;
  status: 'PASS' | 'WARN' | 'FAIL';
  timestamp: string;
  auditor: string;
  readings: number[];
  calibrationSnapshot?: CalibrationSnapshot; 
}

export interface Project {
  id: string;
  name: string;
  lastModified: string;
  gridData: { [col: number]: { [row: number]: string } };
  gridUnits?: { [col: number]: string };
  calibrationOverrides: { [paramId: number]: CalibrationSnapshot };
}
