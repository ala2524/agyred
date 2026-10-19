package cmd

import (
	"fmt"
	"os"

	"github.com/spf13/cobra"
	"github.com/ala2524/agyred/internal/aliases"
	"github.com/ala2524/agyred/internal/db"
)

var RootCmd = &cobra.Command{
	Use:     "agyred",
	Aliases: []string{"agm"},
	Short:   "agyred — multi-account CLI for Antigravity (agy / IDE / desktop)",
	Long: `agyred — multi-account CLI for Antigravity (agy / IDE / desktop)

Data: ~/.antigravity-agent/`,
	SilenceErrors: true,
	SilenceUsage:  true,
	PersistentPreRunE: func(cmd *cobra.Command, args []string) error {
		// Do not auto-initialize database if help command is invoked
		if cmd.Name() == "help" {
			return nil
		}
		// Ensure that the help flags do not trigger db initialization
		if flag, err := cmd.Flags().GetBool("help"); err == nil && flag {
			return nil
		}
		return db.EnsureStore()
	},
}

func Execute() {
	if err := RootCmd.Execute(); err != nil {
		fmt.Fprintf(os.Stderr, "error: %v\n", err)
		os.Exit(1)
	}
}

func resolve(pattern string) string {
	return aliases.Resolve(pattern)
}
