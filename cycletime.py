import json
import argparse
import sys
from typing import Dict, Any, Optional

def find_face_width(data: Dict[str, Any]) -> Optional[float]:
    """
    Extract face width value from the JSON data structure
    
    Args:
        data: Parsed JSON data
        
    Returns:
        Face width value in mm, or None if not found
    """
    try:
        extracted_data = data.get('extracted_data', {})
        dimensions = extracted_data.get('dimensions', [])
        
        for dimension in dimensions:
            if dimension.get('id') == 'dim_face_width':
                return float(dimension.get('value', 0))
                
        for dimension in dimensions:
            leaders = dimension.get('leaders', [])
            for leader in leaders:
                if 'face' in leader.lower() and ('gear' in leader.lower() or 'rim' in leader.lower()):
                    return float(dimension.get('value', 0))
                    
        return None
        
    except (KeyError, ValueError, TypeError) as e:
        print(f"Error extracting face width: {e}")
        return None

def calculate_length_of_cut(face_width: float, approach: float = 1.0, overtravel: float = 1.0) -> float:
    """
    Calculate the total length of cut
    
    Args:
        face_width: Face width of the part in mm
        approach: Approach allowance in mm (default: 1.0)
        overtravel: Overtravel allowance in mm (default: 1.0)
        
    Returns:
        Total length of cut in mm
    """
    return face_width + approach + overtravel

def calculate_cycle_time(length_of_cut: float, feed_rate: float, rpm: float) -> float:
    """
    Calculate the cycle time using the formula: T = L / (f * N)
    
    Args:
        length_of_cut: Length of cut in mm
        feed_rate: Feed rate in mm/rev
        rpm: Number of revolutions per minute (RPM)
        
    Returns:
        Cycle time in minutes
    """
    if feed_rate <= 0 or rpm <= 0:
        raise ValueError("Feed rate and RPM must be greater than 0")
    
    return length_of_cut / (feed_rate * rpm)

def print_results(face_width: float, approach: float, overtravel: float, length_of_cut: float, 
                 tolerance: str = None, feed_rate: float = None, rpm: float = None, cycle_time: float = None):
    """
    Print formatted results
    """
    print("=" * 60)
    print("MACHINING CALCULATION RESULTS")
    print("=" * 60)
    
    print("LENGTH OF CUT CALCULATION:")
    print(f"  Face Width: {face_width} mm", end="")
    if tolerance:
        print(f" (tolerance: {tolerance})")
    else:
        print()
    print(f"  Approach Allowance: {approach} mm")
    print(f"  Overtravel Allowance: {overtravel} mm")
    print(f"  Length of Cut: {length_of_cut} mm")
    print(f"  Formula: {face_width} + {approach} + {overtravel} = {length_of_cut} mm")
    
    if feed_rate is not None and rpm is not None and cycle_time is not None:
        print("\n" + "-" * 40)
        print("CYCLE TIME CALCULATION:")
        print(f"  Feed Rate (f): {feed_rate} mm/rev")
        print(f"  RPM (N): {rpm} rev/min")
        print(f"  Cycle Time (T): {cycle_time:.4f} minutes")
        print(f"  Cycle Time (T): {cycle_time * 60:.2f} seconds")
        print(f"  Formula: T = L / (f × N) = {length_of_cut} / ({feed_rate} × {rpm}) = {cycle_time:.4f} min")
    
    print("=" * 60)

def main():
    parser = argparse.ArgumentParser(
        description='Calculate length of cut and cycle time from JSON gear data',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('json_file', help='Path to JSON file containing gear data')
    parser.add_argument('-a', '--approach', type=float, default=1.0,
                       help='Approach allowance in mm (default: 1.0)')
    parser.add_argument('-o', '--overtravel', type=float, default=1.0,
                       help='Overtravel allowance in mm (default: 1.0)')
    parser.add_argument('-f', '--feed-rate', type=float,
                       help='Feed rate in mm/rev (required for cycle time calculation)')
    parser.add_argument('-n', '--rpm', type=float,
                       help='RPM - revolutions per minute (required for cycle time calculation)')
    parser.add_argument('-v', '--verbose', action='store_true',
                       help='Show detailed information about the extraction process')
    
    args = parser.parse_args()
    
    try:
        with open(args.json_file, 'r', encoding='utf-8') as file:
            data = json.load(file)
            
        if args.verbose:
            print("JSON file loaded successfully")
            
        face_width = find_face_width(data)
        
        if face_width is None:
            print("Error: Could not find face width in the JSON data")
            print("Please check that the JSON contains dimension data with face width information")
            sys.exit(1)
            
        tolerance = None
        try:
            dimensions = data.get('extracted_data', {}).get('dimensions', [])
            for dim in dimensions:
                if dim.get('id') == 'dim_face_width':
                    tolerance = dim.get('tolerance')
                    break
        except:
            pass
            
        if args.verbose:
            print(f"Face width extracted: {face_width} mm")
            if tolerance:
                print(f"Face width tolerance: {tolerance}")
                
        length_of_cut = calculate_length_of_cut(face_width, args.approach, args.overtravel)
        
        cycle_time = None
        if args.feed_rate is not None and args.rpm is not None:
            try:
                cycle_time = calculate_cycle_time(length_of_cut, args.feed_rate, args.rpm)
                if args.verbose:
                    print(f"Cycle time calculated: {cycle_time:.4f} minutes")
            except ValueError as e:
                print(f"Error calculating cycle time: {e}")
                sys.exit(1)
        elif args.feed_rate is not None or args.rpm is not None:
            print("Warning: Both feed rate (-f) and RPM (-n) are required for cycle time calculation")
        
        print_results(face_width, args.approach, args.overtravel, length_of_cut, tolerance, 
                     args.feed_rate, args.rpm, cycle_time)
        
    except FileNotFoundError:
        print(f"Error: File '{args.json_file}' not found")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON format - {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()

# # Calculate both length of cut and cycle time
# python length_of_cut.py data.json --feed-rate 0.5 --rpm 1200

# # Short form
# python length_of_cut.py data.json -f 0.3 -n 800

# # With custom approach/overtravel and cycle time
#python length_of_cut.py data.json -f 0.3 -n 800 -a 1.2 -o 1.5

#   python cycletime.py  outputs/drawings/5e339431-31ee-4dbd-85d2-ea97deb6b0d4/5e339431-31ee-4dbd-85d2-ea97deb6b0d4.json