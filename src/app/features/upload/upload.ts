import {
  Component,
  OnDestroy,
  Output,
  EventEmitter,
  ViewChild,
  ElementRef
} from '@angular/core';

import { CommonModule } from '@angular/common';

import {
  HttpClient,
  HttpHeaders
} from '@angular/common/http';

import { Router, RouterModule } from '@angular/router';

const BASE_URL =
  'https://facelift-correct-simple.ngrok-free.dev/api/google';

export interface AnalysisResult {
  task_id: string;
  status: string;
  filename: string;
  file_size: number;
  extracted_data: any;
}

@Component({
  selector: 'app-upload',
  imports: [CommonModule, RouterModule],
  templateUrl: './upload.html',
  styleUrl: './upload.scss',
})

export class Upload implements OnDestroy {

  @Output()
  analysisComplete = new EventEmitter<AnalysisResult>();

  @ViewChild('fileInput')
  fileInput!: ElementRef<HTMLInputElement>;

  selectedFile: File | null = null;
  previewUrl: string | null = null;

  isDragOver = false;
  isProcessing = false;

  uploadProgress = 0;

  processingMessage = 'Uploading drawing…';

  toastMessage = '';
  toastType: 'error' | 'success' = 'error';

  taskId = '';

  private pollTimeout?: any;
  private progressInterval?: any;
  private toastTimeout?: any;

  readonly messages = [
    'Uploading drawing…',
    'Parsing drawing views…',
    'Extracting gear table data…',
    'Reading dimensions & tolerances…',
    'Analysing spline features…',
    'Compiling results…'
  ];

  private msgIndex = 0;

  // API Headers
  private headers = new HttpHeaders({
    'Accept': 'application/json',
    'ngrok-skip-browser-warning': 'true'
  });
  private pollAttempts = 0;

  constructor(
    private http: HttpClient,
    private router: Router
  ) {}

  // ───────── Toast ─────────

  showToast(
    message: string,
    type: 'error' | 'success' = 'error'
  ) {
    this.toastMessage = message;
    this.toastType = type;

    clearTimeout(this.toastTimeout);

    this.toastTimeout = setTimeout(() => {
      this.toastMessage = '';
    }, 4000);
  }

  // ───────── Drag & Drop ─────────

  onDragOver(e: DragEvent) {
    e.preventDefault();
    this.isDragOver = true;
  }

  onDragLeave(e: DragEvent) {
    e.preventDefault();
    this.isDragOver = false;
  }

  onDrop(e: DragEvent) {
    e.preventDefault();
    this.isDragOver = false;

    const file = e.dataTransfer?.files?.[0];

    if (file) {
      this.setFile(file);
    }
  }

  onFileSelected(e: Event) {
    const input = e.target as HTMLInputElement;
    const file = input.files?.[0];

    if (file) {
      this.setFile(file);
    }
  }

  setFile(file: File) {
    if (!file.type.startsWith('image/')) {
      this.showToast(
        'Please upload an image file (PNG, JPG, WEBP).'
      );
      return;
    }

    this.selectedFile = file;

    const reader = new FileReader();

    reader.onload = () => {
      this.previewUrl = reader.result as string;
    };

    reader.readAsDataURL(file);
  }

  clearFile(e: MouseEvent) {
    e.stopPropagation();

    // Stop any in-progress polling
    clearTimeout(this.pollTimeout);

    this.selectedFile = null;
    this.previewUrl = null;
    this.taskId = '';
    this.toastMessage = '';

    // Reset input so the same file can be re-selected
    if (this.fileInput?.nativeElement) {
      this.fileInput.nativeElement.value = '';
    }
  }

  // ───────── Upload ─────────

  uploadAndAnalyse() {
    if (!this.selectedFile || this.isProcessing) {
      return;
    }

    this.toastMessage = '';

    const fd = new FormData();
    fd.append('file', this.selectedFile);

    this.http.post<{ task_id: string }>(
      `${BASE_URL}/upload`,
      fd,
      { headers: this.headers }
    )
    .subscribe({

      next: (res) => {
        // Enter processing state only after successful upload
        this.isProcessing = true;
        this.uploadProgress = 0;
        this.processingMessage = this.messages[0];
        this.msgIndex = 0;

        this.startProgressAnimation();

        this.taskId = res.task_id;
        this.pollStatus(res.task_id);
      },

      error: (err) => {
        this.showToast(
          'Upload failed: ' +
          (err.error?.detail || err.message)
        );
      }

    });
  }

  // ───────── Progress Animation ─────────

  private startProgressAnimation() {
    let tick = 0;

    this.progressInterval = setInterval(() => {
      tick++;

      if (this.uploadProgress < 90) {
        this.uploadProgress = Math.min(
          90,
          this.uploadProgress + Math.random() * 3
        );
      }

      if (
        tick % 16 === 0 &&
        this.msgIndex < this.messages.length - 1
      ) {
        this.msgIndex++;
        this.processingMessage = this.messages[this.msgIndex];
      }

    }, 250);
  }

  // ───────── Poll Status ─────────

  private pollStatus(taskId: string) {
    this.http.get<any>(
      `${BASE_URL}/status/${taskId}`,
      { headers: this.headers }
    )
    .subscribe({

      next: (res) => {
        if (res.status === 'completed'|| res.status === 'completed_with_errors') {
          // Done — fetch result once, no more polling
          this.fetchResult(taskId);
        } else if (res.status === 'failed') {
          // Failed — stop everything
          this.handleError(
            'Processing failed on server.'
          );
        } else {
          // Still pending — schedule exactly one more check
          this.pollTimeout = setTimeout(() => {
            this.pollStatus(taskId);
          }, 2000);
        }
      },

      error: (err) => {
        this.handleError(
          'Status check failed: ' +
          (err.message || 'Network error')
        );
      }

    });
  }

  // ───────── Get Result ─────────

  // private fetchResult(taskId: string) {
  //   clearTimeout(this.pollTimeout); // safety net

  //   this.http.get<AnalysisResult>(
  //     `${BASE_URL}/result/${taskId}?include_data=true`,
  //     { headers: this.headers }
  //   )
  //   .subscribe({

  //     next: (res) => {
  //       clearInterval(this.progressInterval);

  //       this.uploadProgress = 100;
  //       this.processingMessage = 'Analysis complete!';

  //       setTimeout(() => {
  //         this.isProcessing = false;
  //         this.analysisComplete.emit(res);
  //       }, 800);
  //     },

  //     error: (err) => {
  //       this.handleError(
  //         'Could not fetch results: ' +
  //         (err.message || 'Network error')
  //       );
  //     }

  //   });
  // }


private fetchResult(taskId: string) {
  clearTimeout(this.pollTimeout);
  this.pollAttempts = 0;

  this.http.get<AnalysisResult>(
    `${BASE_URL}/result/${taskId}?include_data=true`,
    { headers: this.headers }
  )
  .subscribe({

    next: (res) => {
      clearInterval(this.progressInterval);

      this.uploadProgress = 100;
      this.processingMessage = 'Analysis complete!';

      setTimeout(() => {
        this.isProcessing = false;
        this.analysisComplete.emit(res);
        this.router.navigate(['/analysis', res.task_id]);


        // Warn user if partial result
        if (res.status === 'completed_with_errors') {
          this.showToast(
            'Analysis completed with some errors — some data may be incomplete.',
            'error'
          );
        }
      }, 800);
    },

    error: (err) => {
      this.handleError(
        'Could not fetch results: ' +
        (err.message || 'Network error')
      );
    }

  });
}

  // ───────── Error ─────────

  private handleError(msg: string) {
    clearTimeout(this.pollTimeout); // stop any pending poll
    clearInterval(this.progressInterval);

    this.isProcessing = false;
    this.uploadProgress = 0;
    this.taskId = '';

    this.showToast(msg);
  }

  // ───────── Helpers ─────────

  get ringOffset(): number {
    const circumference = 150.796;
    return (
      circumference -
      (this.uploadProgress / 100) * circumference
    );
  }

  formatFileSize(bytes: number): string {
    if (bytes < 1024) {
      return `${bytes} B`;
    }

    if (bytes < 1024 * 1024) {
      return `${(bytes / 1024).toFixed(1)} KB`;
    }

    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  ngOnDestroy() {
    clearTimeout(this.pollTimeout);
    clearInterval(this.progressInterval);
    clearTimeout(this.toastTimeout);
  }

}