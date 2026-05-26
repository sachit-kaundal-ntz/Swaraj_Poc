import { ComponentFixture, TestBed } from '@angular/core/testing';

import { Blueprint } from './blueprint';

describe('Blueprint', () => {
  let component: Blueprint;
  let fixture: ComponentFixture<Blueprint>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [Blueprint],
    }).compileComponents();

    fixture = TestBed.createComponent(Blueprint);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
