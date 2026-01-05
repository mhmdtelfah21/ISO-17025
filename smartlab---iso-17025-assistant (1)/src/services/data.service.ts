
import { Injectable, signal, computed } from '@angular/core';
import { Parameter, Calibration, Result, Project } from '../models';

@Injectable({ providedIn: 'root' })
export class DataService {
  // User & App State
  user = signal({ username: 'Admin', password: 'password123' });
  currentView = signal<'workbench' | 'settings' | 'about'>('workbench');
  
  isReadOnly = computed(() => this.user().username === 'Auditor');

  parameters = signal<Parameter[]>([]);
  calibrations = signal<Calibration[]>([]);
  results = signal<Result[]>([]);
  projects = signal<Project[]>([]);
  
  private nextResultId = 1;

  constructor() {
    this.seedDefaults();
  }

  private seedDefaults() {
    const defaultParams: Omit<Parameter, 'id'>[] = [
      { name: "H2S", unit: "ppb", warnLimit: 10, critLimit: 20 },
      { name: "SO2", unit: "ppb", warnLimit: 75, critLimit: 100 },
      { name: "NO2", unit: "ppb", warnLimit: 40, critLimit: 80 },
      { name: "PM2.5", unit: "ug/m3", warnLimit: 35, critLimit: 50 },
      { name: "PM10", unit: "ug/m3", warnLimit: 150, critLimit: 200 },
      { name: "TVOC", unit: "ppb", warnLimit: 200, critLimit: 500 },
      { name: "CO", unit: "ppm", warnLimit: 9, critLimit: 15 },
      { name: "O3", unit: "ppb", warnLimit: 50, critLimit: 80 },
      { name: "Temperature", unit: "C", warnLimit: 45, critLimit: 50 },
      { name: "Humidity", unit: "%", warnLimit: 85, critLimit: 90 }
    ];
    this.parameters.set(defaultParams.map((p, i) => ({ ...p, id: i + 1 })));
  }

  // --- Parameters ---
  addParameter(param: Omit<Parameter, 'id'>) {
    this.parameters.update(params => {
      const newId = (params.length > 0) ? Math.max(...params.map(p => p.id)) + 1 : 1;
      return [...params, { ...param, id: newId }];
    });
  }

  updateParameter(updatedParam: Parameter) {
    this.parameters.update(params => 
      params.map(p => p.id === updatedParam.id ? updatedParam : p)
    );
  }

  removeParameter(paramId: number) {
    this.parameters.update(params => params.filter(p => p.id !== paramId));
    this.calibrations.update(cals => cals.filter(c => c.paramId !== paramId));
  }

  // --- Calibrations ---
  getActiveCalibrationForParam(paramId: number): Calibration | undefined {
    return this.calibrations().find(c => c.paramId === paramId && c.active);
  }

  getCalibrationsForParam(paramId: number): Calibration[] {
    return this.calibrations().filter(c => c.paramId === paramId);
  }

  saveCalibration(cal: Omit<Calibration, 'id' | 'active'>) {
    this.calibrations.update(cals => {
      const updatedCals = cals.map(c => c.paramId === cal.paramId ? { ...c, active: false } : c);
      const newId = (cals.length > 0) ? Math.max(...cals.map(c => c.id)) + 1 : 1;
      updatedCals.push({ ...cal, id: newId, active: true });
      return updatedCals;
    });
  }
  
  removeCalibration(calibrationId: number) {
    this.calibrations.update(cals => cals.filter(c => c.id !== calibrationId));
  }

  // --- Results ---
  addResults(newResults: Omit<Result, 'id'>[]) {
    this.results.update(currentResults => {
      const resultsToAdd = newResults.map(r => ({...r, id: this.nextResultId++}));
      return [...resultsToAdd, ...currentResults];
    });
  }

  // --- Projects ---
  saveProject(project: Project) {
    this.projects.update(projs => {
      const existingIndex = projs.findIndex(p => p.id === project.id);
      if (existingIndex >= 0) {
        const updated = [...projs];
        updated[existingIndex] = project;
        return updated;
      }
      return [project, ...projs];
    });
  }

  deleteProject(projectId: string) {
    this.projects.update(projs => projs.filter(p => p.id !== projectId));
  }
}
