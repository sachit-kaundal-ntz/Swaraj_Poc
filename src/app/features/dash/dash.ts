import { Component, OnInit } from '@angular/core';
import { Router, RouterModule } from '@angular/router';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';




interface Analysis {

  id: string;

  filename: string;

  uploadDate: string | null;

  fileSize: number | null;

  status: 'completed' | 'processing' | 'failed' | null;

  specs: {
    gear_family?: string;
    module?: number;
    teeth?: number;
  };

  cost_breakdown: {
    total_cost?: number;
  };

}

@Component({
  selector: 'app-dash',
  imports: [CommonModule, RouterModule,FormsModule],
  templateUrl: './dash.html',
  styleUrl: './dash.scss',
})



export class Dash implements OnInit {
  analyses: Analysis[] = [];
  isLoading = true;
  searchTerm = '';
  deleteTargetId: string | null = null;
 
  stats = { total: 0, completed: 0, processing: 0, gearFamilies: 0 };
 
  // Mock data — replace with API service call
  private mockAnalyses: Analysis[] = [
    {
      id: 'a1',
      filename: 'helical_gear_ASSY_v3.dwg',
      uploadDate: '2025-06-10T10:22:00Z',
      fileSize: 2430000,
      status: 'completed',
      specs: { gear_family: 'HELICAL', module: 2.5, teeth: 48 },
      cost_breakdown: { total_cost: 342.80 }
    },
    {
      id: 'a2',
      filename: 'spur_pinion_rev2.dxf',
      uploadDate: '2025-06-08T14:05:00Z',
      fileSize: 890000,
      status: 'completed',
      specs: { gear_family: 'SPUR', module: 3, teeth: 24 },
      cost_breakdown: { total_cost: 187.50 }
    },
    {
      id: 'a3',
      filename: 'bevel_gear_drawing.pdf',
      uploadDate: '2025-06-07T09:15:00Z',
      fileSize: 4200000,
      status: 'processing',
      specs: { gear_family: 'BEVEL' },
      cost_breakdown: {}
    },
    {
      id: 'a4',
      filename: 'worm_gear_set_A.png',
      uploadDate: '2025-06-05T16:40:00Z',
      fileSize: 1120000,
      status: 'failed',
      specs: {},
      cost_breakdown: {}
    }
  ];
 
  constructor(private router: Router) {}
 
  ngOnInit(): void {
    this.loadAnalyses();
  }
 
  loadAnalyses(): void {
    this.isLoading = true;
    // Simulate API call
    setTimeout(() => {
      this.analyses = this.mockAnalyses;
      this.computeStats();
      this.isLoading = false;
    }, 800);
  }
 
  computeStats(): void {
    const families = new Set(
      this.analyses
        .map(a => a.specs?.gear_family)
        .filter(Boolean)
    );
    this.stats = {
      total: this.analyses.length,
      completed: this.analyses.filter(a => a.status === 'completed').length,
      processing: this.analyses.filter(a => a.status === 'processing').length,
      gearFamilies: families.size
    };
  }
 
  get filteredAnalyses(): Analysis[] {
    if (!this.searchTerm.trim()) return this.analyses;
    const term = this.searchTerm.toLowerCase();
    return this.analyses.filter(a => a.filename.toLowerCase().includes(term));
  }
 
  goToDetail(id: string): void {
    this.router.navigate(['/analysis', id]);
  }
 
  // getStatusClass(status: string): string {
  //   return {
  //     completed: 'status-badge--completed',
  //     processing: 'status-badge--processing',
  //     failed: 'status-badge--failed'
  //   }[status] ?? '';
  // }
 
getStatusClass(status: string | null): string {

  return {

    completed: 'status-badge--completed',

    processing: 'status-badge--processing',

    failed: 'status-badge--failed'

  }[status ?? ''] ?? '';

}

  getFileIcon(filename: string): string {
    const ext = filename.split('.').pop()?.toLowerCase();
    const map: Record<string, string> = {
      dwg: '📐', dxf: '📐', pdf: '📄',
      png: '🖼', jpg: '🖼', jpeg: '🖼', webp: '🖼'
    };
    return map[ext ?? ''] ?? '📁';
  }
 
  // formatSize(bytes: number): string {
  //   if (bytes >= 1_000_000) return `${(bytes / 1_000_000).toFixed(1)} MB`;
  //   if (bytes >= 1_000) return `${(bytes / 1_000).toFixed(0)} KB`;
  //   return `${bytes} B`;
  // }
 
formatSize(bytes: number | null): string {

  if (bytes == null) {
    return '--';
  }

  if (bytes >= 1_000_000) {
    return `${(bytes / 1_000_000).toFixed(1)} MB`;
  }

  if (bytes >= 1_000) {
    return `${(bytes / 1_000).toFixed(0)} KB`;
  }

  return `${bytes} B`;

}


  confirmDelete(id: string, event: Event): void {
    event.stopPropagation();
    this.deleteTargetId = id;
  }
 
  cancelDelete(): void {
    this.deleteTargetId = null;
  }
 
  deleteAnalysis(): void {
    if (!this.deleteTargetId) return;
    // Replace with API call: DELETE /api/analyses/:id
    this.analyses = this.analyses.filter(a => a.id !== this.deleteTargetId);
    this.computeStats();
    this.deleteTargetId = null;
  }
}