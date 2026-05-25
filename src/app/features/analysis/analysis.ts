import { CommonModule } from '@angular/common';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Component, OnDestroy, OnInit } from '@angular/core';
import { ActivatedRoute, Router, RouterModule } from '@angular/router';

const BASE_URL = 'https://facelift-correct-simple.ngrok-free.dev/api/google';

const HEADERS = new HttpHeaders({
  'Accept': 'application/json',
  'ngrok-skip-browser-warning': 'true'
});

@Component({
  selector: 'app-analysis',
  imports: [CommonModule, RouterModule],
  templateUrl: './analysis.html',
  styleUrl: './analysis.scss',
})
export class AnalysisComponent implements OnInit, OnDestroy {

  taskId = '';
  result: any = null;
  loading = true;
  errorMsg = '';

  // Poll for status
  private pollTimeout?: any;

  constructor(
    private route: ActivatedRoute,
    private router: Router,
    private http: HttpClient
  ) {}

  ngOnInit(): void {
    this.taskId = this.route.snapshot.paramMap.get('id') ?? '';
    if (!this.taskId) {
      this.errorMsg = 'No task ID provided.';
      this.loading = false;
      return;
    }
    this.pollStatus();
  }

  ngOnDestroy(): void {
    clearTimeout(this.pollTimeout);
  }

  // ───────── Poll Status ─────────

  private pollStatus(): void {
    this.http.get<any>(
      `${BASE_URL}/status/${this.taskId}`,
      { headers: HEADERS }
    ).subscribe({
      next: (res) => {
        if (
          res.status === 'completed' ||
          res.status === 'completed_with_errors'
        ) {
          this.fetchResult();
        } else if (res.status === 'failed') {
          this.loading = false;
          this.errorMsg = 'Processing failed on server.';
        } else {
          // Still pending — check again in 2s
          this.pollTimeout = setTimeout(() => {
            this.pollStatus();
          }, 2000);
        }
      },
      error: (err) => {
        this.loading = false;
        this.errorMsg = 'Status check failed: ' + (err.message || 'Network error');
      }
    });
  }

  // ───────── Fetch Result ─────────

  private fetchResult(): void {
    this.http.get<any>(
      `${BASE_URL}/result/${this.taskId}?include_data=true`,
      { headers: HEADERS }
    ).subscribe({
      next: (res) => {
        this.result = res;
        this.loading = false;
      },
      error: (err) => {
        this.loading = false;
        this.errorMsg = 'Could not fetch results: ' + (err.message || 'Network error');
      }
    });
  }

  // ───────── Getters ─────────

  get data() {
    return this.result?.extracted_data;
  }

  get hasExtractionError(): boolean {
    return !!this.data?.error;
  }

  get extractionError(): string {
    const err = this.data?.error ?? '';
    if (err.includes('429') || err.includes('quota')) {
      return 'Google Gemini API quota exceeded. Please wait a few minutes and try again.';
    }
    return 'Extraction failed due to an API error. Please try reprocessing.';
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

  // ───────── Actions ─────────

  downloadJSON(): void {
    window.open(`${BASE_URL}/download/${this.taskId}/json`, '_blank');
  }

  downloadCSV(): void {
    window.open(`${BASE_URL}/download/${this.taskId}/csv`, '_blank');
  }

  reprocess(): void {
    this.loading = true;
    this.errorMsg = '';
    this.result = null;
    this.http.post(`${BASE_URL}/reprocess/${this.taskId}`, {}, { headers: HEADERS })
      .subscribe({
        next: () => {
          this.pollTimeout = setTimeout(() => this.pollStatus(), 2000);
        },
        error: () => {
          this.loading = false;
          this.errorMsg = 'Reprocess request failed.';
        }
      });
  }

  goBack(): void {
    this.router.navigate(['/upload']);
  }

  copied = false;
  copyTaskId(): void {
    navigator.clipboard.writeText(this.taskId).then(() => {
      this.copied = true;
      setTimeout(() => this.copied = false, 2000);
    });
  }

  activeTab = 'tables';
}