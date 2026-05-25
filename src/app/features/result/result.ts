import { Component, EventEmitter, Input, OnInit, Output } from '@angular/core';
import { AnalysisResult } from '../upload/upload';
import { HttpClient } from '@angular/common/http';
import { FormsModule } from '@angular/forms';
import { CommonModule } from '@angular/common';

type TabDef = {
  id: string;
  label: string;
  icon: string;
  count: number;
};

@Component({
  selector: 'app-result',
  imports: [FormsModule,CommonModule],
  templateUrl: './result.html',
  styleUrl: './result.scss',
})


export class Result implements OnInit {
 
  @Input() result!: AnalysisResult;
  @Output() back = new EventEmitter<void>();
 
  activeTab = 'tables';
  isReprocessing = false;
  copied = false;
 
BASE_URL = 'https://facelift-correct-simple.ngrok-free.dev/api/google';


  readonly tabIconMap: Record<string, string> = {
    tables:     '<rect x="1" y="2" width="14" height="12" rx="1.5" stroke="currentColor" stroke-width="1.3"/><path d="M1 6h14M5 2v12" stroke="currentColor" stroke-width="1.3"/>',
    dimensions: '<circle cx="8" cy="8" r="6" stroke="currentColor" stroke-width="1.3"/><path d="M8 5v6M5 8h6" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>',
    features:   '<path d="M3 5l5-3 5 3v6l-5 3-5-3V5z" stroke="currentColor" stroke-width="1.3"/>',
    metadata:   '<circle cx="8" cy="8" r="6" stroke="currentColor" stroke-width="1.3"/><path d="M8 7v5M8 5.5v.5" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>'
  };
 
  get data() { return this.result?.extracted_data; }
 
  get tabs(): TabDef[] {
    return [
      { id: 'tables',     label: 'Tables',     icon: this.tabIconMap['tables'],     count: this.data?.tables?.length ?? 0 },
      { id: 'dimensions', label: 'Dimensions', icon: this.tabIconMap['dimensions'], count: this.data?.dimensions?.length ?? 0 },
      { id: 'features',   label: 'Features',   icon: this.tabIconMap['features'],   count: this.data?.features?.length ?? 0 },
      { id: 'metadata',   label: 'Metadata',   icon: this.tabIconMap['metadata'],   count: 0 },
    ];
  }
 
  get tableCount()     { return this.data?.tables?.length ?? 0; }
  get dimensionCount() { return this.data?.dimensions?.length ?? 0; }
  get featureCount()   { return this.data?.features?.length ?? 0; }
  get viewCount()      { return this.data?.views?.length ?? 0; }
 
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
 
  constructor(private http: HttpClient) {}
 
  ngOnInit() {}
 
  onBack() { this.back.emit(); }
 
  formatTableId(id: string): string {
    return id.replace(/^tbl_/, '').replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
  }
 
  formatDimId(id: string): string {
    return id.replace(/^dim_/, '').replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
  }
 
  formatFeatureId(id: string): string {
    return id.replace(/^feat_/, '').replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
  }
 
  formatFileSize(bytes: number): string {
    if (!bytes) return '—';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }
 
  downloadJSON() {
    window.open(`${this.BASE_URL}/download/${this.result.task_id}/json`, '_blank');
  }
 
  downloadCSV() {
    window.open(`${this.BASE_URL}/download/${this.result.task_id}/csv`, '_blank');
  }
 
  reprocess() {
    if (this.isReprocessing) return;
    this.isReprocessing = true;
    this.http.post(`${this.BASE_URL}/reprocess/${this.result.task_id}`, {}).subscribe({
      next: () => {
        setTimeout(() => {
          this.isReprocessing = false;
          this.back.emit(); // go back to upload so user re-uploads or polls
        }, 1500);
      },
      error: () => { this.isReprocessing = false; }
    });
  }
 

  get hasExtractionError(): boolean {
  return !!this.data?.error;
}

get extractionError(): string {
  const err = this.data?.error ?? '';
  // Return a clean user-friendly message
  if (err.includes('429') || err.includes('quota')) {
    return 'Google Gemini API quota exceeded. Please wait a few minutes and try again.';
  }
  if (err.includes('error')) {
    return 'Extraction failed due to an API error. Please try reprocessing.';
  }
  return 'An unknown error occurred during extraction.';
}


  copyTaskId() {
    navigator.clipboard.writeText(this.result.task_id).then(() => {
      this.copied = true;
      setTimeout(() => this.copied = false, 2000);
    });
  }
}