import { CommonModule, NgIf } from '@angular/common';
import { Component } from '@angular/core';
import { FormBuilder, FormGroup, FormsModule, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router } from '@angular/router';

@Component({
  selector: 'app-login',
  imports: [FormsModule, CommonModule, ReactiveFormsModule,NgIf],
  templateUrl: './login.html',
  styleUrl: './login.scss',
})


export class Login {

loginForm!: FormGroup;
  showPassword = false;
  formSubmitted = false;
  
  // Valid credentials
  private readonly VALID_USERNAME = "admin";
  private readonly VALID_PASSWORD = "quiz123";

  constructor(
    private fb: FormBuilder,
    private router: Router
  ) {}

  ngOnInit(): void {
    this.loginForm = this.fb.group({
      email: ['', [Validators.required]],
      password: ['', [Validators.required]],
      rememberMe: [false]
    });
  }

  get email() {
    return this.loginForm.get('email');
  }

  get password() {
    return this.loginForm.get('password');
  }

  togglePassword(): void {
    this.showPassword = !this.showPassword;
  }

  onSubmit(): void {
    this.formSubmitted = true;

    if (this.loginForm.valid) {
      const email = this.loginForm.value.email;
      const password = this.loginForm.value.password;

      // Check credentials and route to dashboard if match
      if (email === this.VALID_USERNAME && password === this.VALID_PASSWORD) {
        // Persist login state so AuthGuard allows navigation
        if (typeof window !== 'undefined') {
          if (this.loginForm.value.rememberMe) {
            localStorage.setItem('isLoggedIn', 'true');
            localStorage.setItem('userEmail', email);
          } else {
            sessionStorage.setItem('isLoggedIn', 'true');
            sessionStorage.setItem('userEmail', email);
          }
        }

        this.router.navigate(['/blue']);
      } else {
        alert('Invalid credentials!');
      }
    }
  }
}
