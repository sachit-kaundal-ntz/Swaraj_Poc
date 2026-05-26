import { CommonModule } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { Router } from '@angular/router';

@Component({
  selector: 'app-landing-page',
  imports: [CommonModule],
  templateUrl: './landing-page.html',
  styleUrl: './landing-page.scss',
})
export class LandingPage implements OnInit {
  isLoggedIn = false;
 
  steps = [
    {
      icon: '📤',
      title: 'Upload Drawing',
      desc: 'Drop any gear drawing — DWG, DXF, PDF, or image file up to 25 MB.'
    },
    {
      icon: '🤖',
      title: 'AI Extraction',
      desc: 'Our model identifies gear family, module, teeth count, tolerances, and GD&T callouts.'
    },
    {
      icon: '⚙️',
      title: 'Cost Modeling',
      desc: 'Material matching, density lookup, machining operations, overhead and margin applied.'
    },
    {
      icon: '📊',
      title: 'Review & Export',
      desc: 'Edit time and rates, adjust material, download JSON or print the full report.'
    }
  ];
 
  capabilities = [
    {
      icon: '🔩',
      title: 'Gear Specifications',
      desc: '17 parameters including module, teeth, pitch diameter, helix angle, pressure angle, and material grade.'
    },
    {
      icon: '📏',
      title: 'Dimensions & Tolerances',
      desc: 'Every geometric feature extracted with its nominal value, unit, and tolerance band.'
    },
    {
      icon: '⊕',
      title: 'GD&T Callouts',
      desc: 'Characteristic type, tolerance zone, datum references, and engineering notes parsed automatically.'
    },
    {
      icon: '🏭',
      title: 'Manufacturing Routing',
      desc: 'Step-by-step operation list with editable cycle times and machine hourly rates.'
    },
    {
      icon: '💰',
      title: 'Cost Breakdown',
      desc: 'Material cost, overhead percentage, and margin percentage — all live-editable with instant totals.'
    },
    {
      icon: '🗂️',
      title: 'Drawing Data Table',
      desc: 'Title block, drawing number, revision, and gear data table extracted verbatim from the print.'
    }
  ];
 
  constructor(private router: Router) {}
 
  ngOnInit(): void {
    // Check auth state from localStorage or auth service
    this.isLoggedIn = !!localStorage.getItem('gearforge_token');
  }
 
  navigate(): void {
    if (this.isLoggedIn) {
      this.router.navigate(['/dashboard']);
    } else {
      this.router.navigate(['/auth']);
    }
  }
}
 