
import { Component, ChangeDetectionStrategy, inject, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule, NgForm } from '@angular/forms';
import { DataService } from '../../services/data.service';
import { CalculationService } from '../../services/calculation.service';
import { Parameter, Calibration, Result, Project, CalibrationSnapshot } from '../../models';
import { CalibrationComponent } from '../calibration/calibration.component';

type WorkbenchTab = 'projects' | 'parameters' | 'measurements' | 'results' | 'documentation';

@Component({
  selector: 'app-analysis',
  templateUrl: './analysis.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [CommonModule, FormsModule, CalibrationComponent],
})
export class AnalysisComponent {
  dataService = inject(DataService);
  calculationService = inject(CalculationService);
  
  // Data Signals
  parameters = this.dataService.parameters;
  results = this.dataService.results;
  projects = this.dataService.projects;

  // Analysis State
  projectName = signal('Untitled Project');
  currentProjectId = signal<string | null>(null); // If working on a saved project
  gridRows = signal(10);
  
  // Grid data: { [colIndex: number]: { [rowIndex: number]: string } }
  gridData = signal<{ [key: number]: { [key: number]: string } }>({});
  
  // Grid Units: { [colIndex: number]: string } - Stores selected input unit for that column
  gridUnits = signal<{ [key: number]: string }>({});
  
  // Calibration Overrides: { [paramId: number]: CalibrationSnapshot }
  calibrationOverrides = signal<{ [paramId: number]: CalibrationSnapshot }>({});

  isGridReady = computed(() => this.parameters().length > 0);

  // UI State
  activeTab = signal<WorkbenchTab>('projects');
  
  // Modals
  editingParam = signal<Parameter | null>(null);
  viewingResult = signal<Result | null>(null);
  isAddingParameter = signal(false);
  
  // Calibration Override Modal State
  overrideParam = signal<Parameter | null>(null);
  overrideFormState = signal<Partial<CalibrationSnapshot>>({});
  
  // Settings Form State
  settingsForm = signal({ newUsername: '', newPassword: '' });

  calibrationStatus = computed(() => {
    const statusMap = new Map<number, boolean>();
    const calibrations = this.dataService.calibrations();
    for (const param of this.parameters()) {
      const hasActiveCal = calibrations.some(c => c.paramId === param.id && c.active);
      statusMap.set(param.id, hasActiveCal);
    }
    return statusMap;
  });
  
  constructor() {
    this.setupGrid();
    // Initialize settings form with current user
    this.settingsForm.set({
      newUsername: this.dataService.user().username,
      newPassword: this.dataService.user().password
    });
  }
  
  setupGrid() {
    this.gridData.set({});
    this.gridUnits.set({});
    this.calibrationOverrides.set({});
    this.projectName.set('Untitled Project');
    this.currentProjectId.set(null);
  }

  // --- Settings Management ---
  saveSettings() {
    const { newUsername, newPassword } = this.settingsForm();
    if (newUsername && newPassword) {
      this.dataService.user.set({ username: newUsername, password: newPassword });
      alert('User settings updated successfully.');
    } else {
      alert('Username and Password cannot be empty.');
    }
  }

  // --- Project History ---
  saveProject() {
    const name = this.projectName().trim() || 'Untitled Project';
    const id = this.currentProjectId() || crypto.randomUUID();
    
    const project: Project = {
      id,
      name,
      lastModified: new Date().toISOString(),
      gridData: this.gridData(),
      gridUnits: this.gridUnits(),
      calibrationOverrides: this.calibrationOverrides()
    };

    this.dataService.saveProject(project);
    this.currentProjectId.set(id);
    alert('Project Saved Successfully!');
  }

  loadProject(project: Project) {
    this.currentProjectId.set(project.id);
    this.projectName.set(project.name);
    this.gridData.set(JSON.parse(JSON.stringify(project.gridData))); // Deep copy
    
    // Load units or default to empty (which falls back to param unit)
    this.gridUnits.set(project.gridUnits ? JSON.parse(JSON.stringify(project.gridUnits)) : {});
    
    this.calibrationOverrides.set(JSON.parse(JSON.stringify(project.calibrationOverrides)));
    this.activeTab.set('measurements');
    this.dataService.currentView.set('workbench'); // Switch view
  }

  deleteProject(projectId: string, event: Event) {
    event.stopPropagation();
    if(confirm('Are you sure you want to delete this project?')) {
       this.dataService.deleteProject(projectId);
       if (this.currentProjectId() === projectId) {
         this.setupGrid();
       }
    }
  }

  // --- Calibration Overrides ---
  openOverrideModal(param: Parameter) {
    const existingOverride = this.calibrationOverrides()[param.id];
    const activeCal = this.dataService.getActiveCalibrationForParam(param.id);

    if (existingOverride) {
      this.overrideFormState.set({ ...existingOverride });
    } else if (activeCal) {
      this.overrideFormState.set({
        device: activeCal.device,
        serial: activeCal.serial,
        certUnc: activeCal.certUnc,
        kFactor: activeCal.kFactor,
        resolution: activeCal.resolution,
        drift: activeCal.drift,
        accuracy: activeCal.accuracy,
        source: 'GLOBAL'
      });
    } else {
      this.overrideFormState.set({ 
        source: 'CUSTOM', 
        device: 'Custom Device',
        kFactor: 2 
      });
    }
    this.overrideParam.set(param);
  }

  saveOverride(snapshot: CalibrationSnapshot) {
    const param = this.overrideParam();
    if (param) {
      this.calibrationOverrides.update(prev => ({
        ...prev,
        [param.id]: snapshot
      }));
    }
    this.overrideParam.set(null);
  }

  clearOverride(paramId: number) {
    this.calibrationOverrides.update(prev => {
      const copy = { ...prev };
      delete copy[paramId];
      return copy;
    });
    this.overrideParam.set(null);
  }

  useHistoricalCalibration(cal: Calibration) {
    const snapshot: CalibrationSnapshot = {
        device: cal.device,
        serial: cal.serial,
        certUnc: cal.certUnc,
        kFactor: cal.kFactor,
        resolution: cal.resolution,
        drift: cal.drift,
        accuracy: cal.accuracy,
        source: 'HISTORY'
    };
    this.saveOverride(snapshot);
  }

  getAvailableCalibrations(paramId: number) {
    return this.dataService.getCalibrationsForParam(paramId);
  }

  // --- Parameter Management ---
  handleSaveParameter(form: NgForm) {
    if (form.valid) {
      const newParam: Omit<Parameter, 'id'> = {
        name: form.value.name,
        unit: form.value.unit,
        warnLimit: form.value.warnLimit || 0,
        critLimit: form.value.critLimit || 0
      };
      this.dataService.addParameter(newParam);
      this.isAddingParameter.set(false);
    }
  }

  updateParameterLimit(param: Parameter, limitType: 'warnLimit' | 'critLimit', event: Event) {
    const input = event.target as HTMLInputElement;
    const value = input.valueAsNumber;
    
    if (!isNaN(value)) {
      const updatedParam = { ...param, [limitType]: value };
      this.dataService.updateParameter(updatedParam);
    }
  }

  removeParameter(paramToRemove: Parameter) {
    this.dataService.removeParameter(paramToRemove.id);
    this.gridData.set({}); 
  }

  // --- Calibration Management (Global) ---
  handleSaveCalibration(calData: Omit<Calibration, 'id' | 'active'>) {
    this.dataService.saveCalibration(calData);
    this.editingParam.set(null); 
    alert('Global calibration profile updated.');
  }

  handleRemoveCalibration(calibrationId: number) {
    this.dataService.removeCalibration(calibrationId);
  }

  // --- Analysis & Units ---
  
  getAvailableUnits(baseUnit: string): string[] {
    const u = baseUnit.toLowerCase();
    if (u === 'ppb' || u === 'ppm') return ['ppb', 'ppm'];
    if (u.includes('ug') || u.includes('mg')) return ['ug/m3', 'mg/m3'];
    if (u === 'c' || u === 'k' || u === 'f') return ['C', 'K', 'F'];
    return [baseUnit];
  }

  onUnitChange(colIndex: number, event: Event) {
    const selectedUnit = (event.target as HTMLSelectElement).value;
    this.gridUnits.update(current => ({
      ...current,
      [colIndex]: selectedUnit
    }));
  }

  onGridInput(col: number, row: number, event: Event) {
    const value = (event.target as HTMLInputElement).value;
    this.gridData.update(currentData => {
      if (!currentData[col]) {
        currentData[col] = {};
      }
      currentData[col][row] = value;
      return {...currentData};
    });
  }
  
  runAnalysis() {
    const newResults: Omit<Result, 'id'>[] = [];
    const currentGridData = this.gridData();
    const currentGridUnits = this.gridUnits();
    const overrides = this.calibrationOverrides();

    for (let c = 0; c < this.parameters().length; c++) {
        const param = this.parameters()[c];
        
        // 1. Check for Override
        let calSnapshot: CalibrationSnapshot | null = null;
        
        if (overrides[param.id]) {
            calSnapshot = overrides[param.id];
        } else {
            // 2. Fallback to Global Active
            const activeCal = this.dataService.getActiveCalibrationForParam(param.id);
            if (activeCal) {
                calSnapshot = {
                    device: activeCal.device,
                    serial: activeCal.serial,
                    certUnc: activeCal.certUnc,
                    kFactor: activeCal.kFactor,
                    resolution: activeCal.resolution,
                    drift: activeCal.drift,
                    accuracy: activeCal.accuracy,
                    source: 'GLOBAL'
                };
            }
        }

        if (!calSnapshot) continue; // Skip if no calibration data available

        const colData = currentGridData[c] || {};
        const readings: number[] = [];
        for (let r = 0; r < this.gridRows(); r++) {
            const val = colData[r];
            if (val && !isNaN(parseFloat(val))) {
                readings.push(parseFloat(val));
            }
        }

        if (readings.length > 0) {
          // Get input unit for this specific column, or default to param unit
          const inputUnit = currentGridUnits[c] || param.unit;
          
          const result = this.calculationService.runAnalysis(
            this.projectName(), 
            param, 
            calSnapshot, 
            readings, 
            inputUnit
          );
          newResults.push(result);
        }
    }
    
    if (newResults.length > 0) {
      this.dataService.addResults(newResults);
      
      // Auto-save project logic when running analysis
      if (confirm('Analysis complete. Save this project state to history?')) {
          this.saveProject();
      }
      
      this.activeTab.set('results'); 
    } else {
      alert('No data or valid calibrations found. Please check your inputs and calibration settings.');
    }
  }
  
  getResultStatusClass(status: string) {
    switch (status) {
      case 'PASS': return 'bg-green-100 text-green-800';
      case 'WARN': return 'bg-yellow-100 text-yellow-800';
      case 'FAIL': return 'bg-red-100 text-red-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  }
}
