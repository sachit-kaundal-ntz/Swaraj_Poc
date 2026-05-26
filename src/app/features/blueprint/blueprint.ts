import { Component, OnDestroy, OnInit, ChangeDetectorRef } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Subscription, interval } from 'rxjs';
import { takeWhile, switchMap } from 'rxjs/operators';
import { CommonModule, UpperCasePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { environment } from '../../core/environments/environment';
import { CellData,TableData,DimensionData,ValidationRule,OperationDetail,ValidationReport,FeatureData,CostBreakdown,ViewData,ExtractedData, PipelineResult, TaskResult, VolumeResult, VolumeSummary } from '../../shared/interface/blueprint-interface';



@Component({
  selector: 'app-blueprint',
  standalone: true,
  imports: [CommonModule, FormsModule, UpperCasePipe],
  templateUrl: './blueprint.html',
  styleUrl: './blueprint.scss',
})
export class Blueprint implements OnInit, OnDestroy {

  apiUrl = environment.apiUrl;

  private headers = new HttpHeaders({
    'Accept': 'application/json',
    'ngrok-skip-browser-warning': 'true'
  });

  // Volume Data
  volumeData: VolumeResult | null = null;
  volumeSummary: VolumeSummary | null = null;
  isVolumeLoading = false;
  volumeError: string | null = null;

  // Pipeline / Cost Data
  pipelineResult: PipelineResult | null = null;
  isPipelineLoading = false;
  pipelineError: string | null = null;

  // Toast
  toastMessage = '';
  toastType: 'error' | 'success' = 'error';
  private toastTimeout?: any;

  // View State
  currentView: 'upload' | 'loading' | 'result' | 'error' = 'upload';

  // File
  selectedFile: File | null = null;
  previewUrl: string | null = null;
  isDragOver = false;

  // Task / Result
  taskId = '';
  result: TaskResult | null = null;
  isProcessing = false;
  isReprocessing = false;
  pollingProgress = 0;
  errorMessage = '';

  // Tabs
  activeTab = 'tables';
  copied = false;
  searchTaskId = '';

  // Loading Messages
  loadingMessage = 'Our structural backend is recognising geometric lines, notes, metadata fields and table borders.';

  private loadingMessages = [
    'Our structural backend is recognising geometric lines, notes, metadata fields and table borders.',
    'Parsing drawing views and extracting gear table data…',
    'Reading dimensions, tolerances and GD&T callouts…',
    'Analysing spline features and assembly order…',
    'Compiling and structuring extraction results…'
  ];
  private msgIdx = 0;
  private msgInterval?: any;

  private pollSub?: Subscription;

  // Tabs Getter
  get tabs() {
    return [
      { id: 'tables', label: 'Tables', count: this.tableCount },
      { id: 'dimensions', label: 'Dimensions', count: this.dimensionCount },
      { id: 'features', label: 'Features', count: this.featureCount },
      { id: 'volume', label: 'Volume & Mass', count: null },
      { id: 'cost', label: 'Cost Analysis', count: null },
      { id: 'metadata', label: 'Metadata' }
    ];
  }

  constructor(
    private http: HttpClient,
    private cdr: ChangeDetectorRef
  ) {}

  ngOnInit(): void {}

  ngOnDestroy(): void {
    this.cancelActivePolling();
    clearInterval(this.msgInterval);
    if (this.toastTimeout) clearTimeout(this.toastTimeout);
  }

  // Toast
  showToast(message: string, type: 'error' | 'success' = 'error'): void {
    this.toastMessage = message;
    this.toastType = type;
    if (this.toastTimeout) clearTimeout(this.toastTimeout);
    this.toastTimeout = setTimeout(() => this.toastMessage = '', 4500);
    this.cdr.detectChanges();
  }

  // Loading Messages
  private startLoadingMessages(): void {
    this.msgIdx = 0;
    this.loadingMessage = this.loadingMessages[0];
    clearInterval(this.msgInterval);
    this.msgInterval = setInterval(() => {
      this.msgIdx = (this.msgIdx + 1) % this.loadingMessages.length;
      this.loadingMessage = this.loadingMessages[this.msgIdx];
      this.cdr.detectChanges();
    }, 3000);
  }

  // File Handling
  onDragOver(e: DragEvent): void {
    e.preventDefault();
    e.stopPropagation();
    this.isDragOver = true;
  }

  onDragLeave(e: DragEvent): void {
    e.preventDefault();
    e.stopPropagation();
    this.isDragOver = false;
  }

  onDrop(e: DragEvent): void {
    e.preventDefault();
    e.stopPropagation();
    this.isDragOver = false;
    if (e.dataTransfer?.files?.length) {
      this.handleFileSelected(e.dataTransfer.files[0]);
    }
  }

  onFileSelected(e: Event): void {
    const input = e.target as HTMLInputElement;
    if (input?.files?.length) {
      this.handleFileSelected(input.files[0]);
    }
  }

  private handleFileSelected(file: File): void {
    this.selectedFile = file;
    if (file.type.startsWith('image/')) {
      const reader = new FileReader();
      reader.onload = () => {
        this.previewUrl = reader.result as string;
        this.cdr.detectChanges();
      };
      reader.readAsDataURL(file);
    }
    this.cdr.detectChanges();
  }

  clearFile(e: Event): void {
    e.stopPropagation();
    this.selectedFile = null;
    this.previewUrl = null;
    this.cdr.detectChanges();
  }

  formatFileSize(bytes?: number): string {
    if (!bytes) return '—';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  // Formatters
  formatTableId(id: string): string {
    return id.replace(/^tbl_/, '').replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
  }

  formatDimId(id: string): string {
    return id.replace(/^dim_/, '').replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
  }

  formatFeatureId(id: string): string {
    return id.replace(/^feat_/, '').replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
  }

  // Getters
  get data(): ExtractedData | undefined {
    return this.result?.extracted_data;
  }

  get hasExtractionError(): boolean {
    return !!(this.data?.error) || !!(this.result?.has_errors);
  }

  get extractionError(): string {
    const err = this.data?.error || '';
    if (err.includes('429') || err.includes('quota')) {
      return 'Gemini API quota exceeded. Please wait a few minutes before retrying.';
    }
    return err || 'Partial extraction completed with errors.';
  }

  get tableCount(): number { return this.data?.tables?.length ?? 0; }
  get dimensionCount(): number { return this.data?.dimensions?.length ?? 0; }
  get featureCount(): number { return this.data?.features?.length ?? 0; }
  get viewCount(): number { return this.data?.views?.length ?? 0; }

  get titleBlockEntries(): { key: string; value: any }[] {
    const tb = this.data?.metadata?.title_block;
    if (!tb) return [];
    return Object.entries(tb)
      .filter(([k]) => k !== 'source')
      .map(([k, v]) => ({
        key: k.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()),
        value: v
      }));
  }

  // Sanitize extracted data before sending to analyze-direct
  private sanitizeExtractedData(data: any): any {
    if (!data) return {};

    const isNumericString = (val: any): boolean => {
      if (typeof val !== 'string') return false;
      return !isNaN(parseFloat(val)) && isFinite(Number(val));
    };

    const sanitizeValue = (val: any): any => {
      if (val === null || val === undefined) return val;
      if (typeof val === 'number') return val;
      if (typeof val === 'string') {
        // Range strings like '0.005-0.015', '±0.05', '+0.01/-0.02' — null them out
        if (/[+\-±\/]/.test(val) && isNaN(Number(val))) return null;
        if (isNumericString(val)) return parseFloat(val);
        return val;
      }
      return val;
    };

    const sanitized = JSON.parse(JSON.stringify(data));

    // Sanitize dimensions
    if (Array.isArray(sanitized.dimensions)) {
      sanitized.dimensions = sanitized.dimensions.map((dim: any) => ({
        ...dim,
        value: sanitizeValue(dim.value)
      }));
    }

    // Sanitize table cells
    if (Array.isArray(sanitized.tables)) {
      sanitized.tables = sanitized.tables.map((table: any) => ({
        ...table,
        cells: Array.isArray(table.cells)
          ? table.cells.map((cell: any) => ({
              ...cell,
              value: sanitizeValue(cell.value)
            }))
          : table.cells
      }));
    }

    return sanitized;
  }

  // API Calls
  uploadAndAnalyse(): void {
    if (!this.selectedFile) return;

    this.isProcessing = true;
    this.currentView = 'loading';
    this.pollingProgress = 10;
    this.startLoadingMessages();
    this.cdr.detectChanges();

    const formData = new FormData();
    formData.append('file', this.selectedFile, this.selectedFile.name);

    this.http.post<any>(`${this.apiUrl}/api/google/upload`, formData).subscribe({
      next: (res) => {
        this.taskId = res?.task_id || res?.id || '';
        if (this.taskId) this.checkOrStartStatusPolling(this.taskId);
        else this.handleError('No task_id received');
      },
      error: () => this.handleError('Upload failed')
    });
  }

  loadPreset(presetId: string): void {
    this.taskId = presetId;
    this.selectedFile = null;
    this.previewUrl = null;
    this.currentView = 'loading';
    this.pollingProgress = 25;
    this.startLoadingMessages();
    this.cdr.detectChanges();
    this.checkOrStartStatusPolling(presetId);
  }

  fetchByTaskId(): void {
    if (!this.searchTaskId?.trim()) return;
    this.taskId = this.searchTaskId.trim();
    this.currentView = 'loading';
    this.pollingProgress = 25;
    this.startLoadingMessages();
    this.cdr.detectChanges();
    this.checkOrStartStatusPolling(this.taskId);
  }

  private checkOrStartStatusPolling(id: string): void {
    this.cancelActivePolling();
    this.http.get<any>(`${this.apiUrl}/api/google/status/${id}`, { headers: this.headers })
      .subscribe({
        next: (res) => {
          if (res.status === 'completed' || res.status === 'completed_with_errors') {
            this.fetchExtractionResults(id);
          } else {
            this.startStatusPolling(id);
          }
        },
        error: () => this.handleError('Failed to check status')
      });
  }

  private startStatusPolling(id: string): void {
    let attempts = 0;
    this.pollSub = interval(2500).pipe(
      switchMap(() => this.http.get<any>(`${this.apiUrl}/api/google/status/${id}`, { headers: this.headers })),
      takeWhile((res) => {
        attempts++;
        if (this.pollingProgress < 90) this.pollingProgress += 6;
        this.cdr.detectChanges();
        return attempts < 40 && !['completed', 'completed_with_errors', 'failed'].includes(res.status);
      }, true)
    ).subscribe({
      next: (res) => {
        if (res.status === 'completed' || res.status === 'completed_with_errors') {
          this.fetchExtractionResults(id);
        } else if (res.status === 'failed') {
          this.handleError('Processing failed on server. Please try again.');
        }
      }
    });
  }

  private fetchExtractionResults(id: string): void {
    this.pollingProgress = 90;
    this.cdr.detectChanges();
    this.http.get<TaskResult>(`${this.apiUrl}/api/google/result/${id}?include_data=true`, { headers: this.headers })
      .subscribe({
        next: (resData) => {
          clearInterval(this.msgInterval);
          this.result = resData;
          this.isProcessing = false;
          this.pollingProgress = 100;
          this.currentView = 'result';
          this.activeTab = 'tables';

          // Load Volume Data and Pipeline/Cost Data
          this.loadVolumeData(id);
          this.loadPipelineData(id);

          this.cdr.detectChanges();
        },
        error: () => this.handleError('Failed to fetch results')
      });
  }

  // Volume Data Loading
  loadVolumeData(taskId: string): void {
    this.isVolumeLoading = true;
    this.volumeError = null;
    this.volumeData = null;
    this.volumeSummary = null;

    this.http.get<any>(`${this.apiUrl}/api/google/volume/${taskId}?include_bore_subtraction=true`, { headers: this.headers })
      .subscribe({
        next: (res) => {
          if (res.status === 'success' && res.volume_result) {
            this.volumeData = res.volume_result;
          }
          this.isVolumeLoading = false;
          this.cdr.detectChanges();
        },
        error: () => {
          this.volumeError = 'Failed to load volume data';
          this.isVolumeLoading = false;
          this.cdr.detectChanges();
        }
      });

    this.http.get<VolumeSummary>(`${this.apiUrl}/api/google/volume/${taskId}/summary`, { headers: this.headers })
      .subscribe({
        next: (summary) => this.volumeSummary = summary,
        error: () => { }
      });
  }

  // Pipeline / Cost Data Loading
  loadPipelineData(taskId: string): void {
    this.isPipelineLoading = true;
    this.pipelineError = null;
    this.pipelineResult = null;

    const sanitized = this.sanitizeExtractedData(this.result?.extracted_data);

    this.http.post<any>(
      `${this.apiUrl}/api/google/analyze-direct`,
      {
        task_id: taskId,
        extracted_data: sanitized
      },
      { headers: this.headers }
    ).subscribe({
      next: (res) => {
        if (res?.pipeline_result) {
          this.pipelineResult = res.pipeline_result;
        }
        this.isPipelineLoading = false;
        this.cdr.detectChanges();
      },
      error: (err) => {
        const detail = err?.error?.detail;
        this.pipelineError = typeof detail === 'string'
          ? `Cost analysis failed: ${detail}`
          : 'Failed to load cost analysis data';
        this.isPipelineLoading = false;
        this.cdr.detectChanges();
      }
    });
  }

  reprocess(): void {
    if (!this.taskId) return;
    this.isReprocessing = true;
    this.cdr.detectChanges();

    this.http.post(`${this.apiUrl}/api/google/reprocess/${this.taskId}`, {}, { headers: this.headers })
      .subscribe({
        next: () => {
          this.currentView = 'loading';
          this.pollingProgress = 30;
          this.isReprocessing = false;
          this.startLoadingMessages();
          this.checkOrStartStatusPolling(this.taskId);
        },
        error: () => {
          this.isReprocessing = false;
          this.handleError('Reprocess failed');
        }
      });
  }

  downloadJSON(): void {
    if (!this.taskId) return;
    window.open(`${this.apiUrl}/api/google/download/${this.taskId}/json`, '_blank');
  }

  downloadCSV(): void {
    if (!this.taskId) return;
    window.open(`${this.apiUrl}/api/google/download/${this.taskId}/csv`, '_blank');
  }

  copyTaskId(): void {
    navigator.clipboard.writeText(this.result?.task_id || '').then(() => {
      this.copied = true;
      this.cdr.detectChanges();
      setTimeout(() => {
        this.copied = false;
        this.cdr.detectChanges();
      }, 2000);
    });
  }

  onBack(): void {
    this.cancelActivePolling();
    clearInterval(this.msgInterval);
    this.currentView = 'upload';
    this.taskId = '';
    this.result = null;
    this.volumeData = null;
    this.volumeSummary = null;
    this.volumeError = null;
    this.pipelineResult = null;
    this.pipelineError = null;
    this.isPipelineLoading = false;
    this.errorMessage = '';
    this.isProcessing = false;
    this.pollingProgress = 0;
    this.cdr.detectChanges();
  }

  private handleError(msg: string): void {
    clearInterval(this.msgInterval);
    this.errorMessage = msg;
    this.isProcessing = false;
    this.currentView = 'error';
    this.cancelActivePolling();
    this.showToast(msg, 'error');
    this.cdr.detectChanges();
  }

  private cancelActivePolling(): void {
    if (this.pollSub) {
      this.pollSub.unsubscribe();
      this.pollSub = undefined;
    }
  }
}