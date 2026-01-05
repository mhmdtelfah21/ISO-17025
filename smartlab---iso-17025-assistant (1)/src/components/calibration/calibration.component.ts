
import { Component, ChangeDetectionStrategy, inject, signal, effect, input, output, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { DataService } from '../../services/data.service';
import { Parameter, Calibration } from '../../models';

const EMPTY_FORM_STATE = {
  device: '',
  serial: '',
  date: new Date().toISOString().split('T')[0],
  certUnc: 0,
  kFactor: 2.0,
  resolution: 0,
  drift: 0,
  accuracy: 0,
};

@Component({
  selector: 'app-calibration',
  templateUrl: './calibration.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [CommonModule, FormsModule],
})
export class CalibrationComponent {
  dataService = inject(DataService);

  // Inputs & Outputs for modal interaction
  parameter = input.required<Parameter>();
  save = output<Omit<Calibration, 'id' | 'active'>>();
  cancel = output<void>();
  remove = output<number>();

  formState = signal(EMPTY_FORM_STATE);

  calibrationHistory = computed(() => {
    const param = this.parameter();
    return this.dataService.calibrations()
      .filter(c => c.paramId === param.id && !c.active)
      .sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());
  });
  
  constructor() {
    effect(() => {
      const param = this.parameter();
      const cal = this.dataService.getActiveCalibrationForParam(param.id);
      if (cal) {
        this.formState.set({
          device: cal.device,
          serial: cal.serial,
          date: cal.date,
          certUnc: cal.certUnc,
          kFactor: cal.kFactor,
          resolution: cal.resolution,
          drift: cal.drift,
          accuracy: cal.accuracy,
        });
      } else {
        this.formState.set(EMPTY_FORM_STATE);
      }
    });
  }

  submitForm() {
    const param = this.parameter();
    if (!param) return;
    
    const newCalibration: Omit<Calibration, 'id' | 'active'> = {
      paramId: param.id,
      ...this.formState(),
    };
    this.save.emit(newCalibration);
  }
}