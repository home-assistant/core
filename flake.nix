{
  description = "A sample Flake for Home Assistant with Python 3.12 & uv";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

outputs = { self, nixpkgs, flake-utils, ... }:
  flake-utils.lib.eachDefaultSystem (system:
    let
      pkgs = import nixpkgs {
        inherit system;
        overlays = [];
      };
      pythonEnv = pkgs.python312.withPackages (ps: with ps; [        
        
        ps.pip # ensure pip exists        
        ps.numpy # Numpy
        # Include any additional Python packages here
      ]);
    in
    {
      devShell = pkgs.mkShell {
        buildInputs = [
          pythonEnv
          
        ];
         shellHook = ''
          
          ./script/setup
          
          # Save the current value of the SHELL variable
          original_shell=$SHELL
          # Run the setup script

          source venv/bin/activate

          
          # Switch back to the original shell
          if [ -x "$original_shell" ]; then
            exec "$original_shell"
          fi
          # Start the virtual environment
          
          '';
        };      
    });
}

