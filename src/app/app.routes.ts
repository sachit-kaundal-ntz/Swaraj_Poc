import { Routes } from '@angular/router';
import { Login } from './features/login/login';
import { Dash } from './features/dash/dash';
import { Upload } from './features/upload/upload';
import { AnalysisComponent } from './features/analysis/analysis';
import { LandingPage } from './features/landing-page/landing-page';
import { Blueprint } from './features/blueprint/blueprint';

export const routes: Routes = [
    {path: '', redirectTo: 'login', pathMatch: 'full'},
    {path: 'login', component: Login},
// { path: 'landing',component:LandingPage },
// { path: 'dash',component: Dash},
// { path: 'upload',component: Upload},
// { path: 'analysis/:id',component:AnalysisComponent},
{path:'blue',component:Blueprint}
];
