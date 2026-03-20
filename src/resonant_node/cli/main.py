"""
Node CLI
========
Command-line interface for running the node.
"""

import asyncio
import logging
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

console = Console()


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
def cli(verbose: bool):
    """ResonantGenesis Node CLI"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


@cli.command()
@click.option(
    "--mode",
    type=click.Choice(["runtime", "index", "storage", "gateway", "full"]),
    default="full",
    help="Node operation mode",
)
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True),
    default=None,
    help="Path to config file",
)
@click.option(
    "--data-dir",
    type=click.Path(),
    default="./data",
    help="Data directory",
)
@click.option(
    "--port",
    type=int,
    default=8080,
    help="API port",
)
@click.option(
    "--chain-rpc",
    type=str,
    default="https://sepolia.base.org",
    help="Chain RPC URL",
)
def start(mode: str, config: str, data_dir: str, port: int, chain_rpc: str):
    """Start the node."""
    from resonant_node.core.node import ResonantNode, NodeConfig, NodeMode
    
    console.print(f"[bold blue]Starting ResonantGenesis Node[/bold blue]")
    console.print(f"Mode: {mode}")
    console.print(f"Data dir: {data_dir}")
    console.print(f"API port: {port}")
    
    # Build config
    node_config = NodeConfig(
        mode=NodeMode(mode),
        data_dir=Path(data_dir),
        chain_rpc=chain_rpc,
        api_port=port,
    )
    
    # Load config file if provided
    if config:
        import yaml
        with open(config) as f:
            file_config = yaml.safe_load(f)
        # Merge configs...
    
    # Create and run node
    node = ResonantNode(node_config)
    
    async def run():
        await node.initialize()
        console.print(f"[green]Node identity: {node.identity.dsid}[/green]")
        console.print(f"[green]API listening on port {port}[/green]")
        
        try:
            await node.start()
        except KeyboardInterrupt:
            console.print("\n[yellow]Shutting down...[/yellow]")
        finally:
            await node.stop()
    
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass


@cli.command()
@click.option("--data-dir", type=click.Path(), default="./data")
def status(data_dir: str):
    """Show node status."""
    from resonant_node.core.identity import NodeIdentity
    
    identity_dir = Path(data_dir) / "identity"
    
    if not identity_dir.exists():
        console.print("[yellow]No node identity found. Run 'start' first.[/yellow]")
        return
    
    async def load():
        return await NodeIdentity.load_or_create(identity_dir)
    
    identity = asyncio.run(load())
    
    table = Table(title="Node Status")
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="green")
    
    table.add_row("DSID", identity.dsid)
    table.add_row("Type", identity.identity_type)
    table.add_row("Public Key", identity.public_key.hex()[:32] + "...")
    table.add_row("Data Dir", str(data_dir))
    
    console.print(table)


@cli.command()
@click.argument("manifest_hash")
@click.option("--input", "-i", "input_json", type=str, default="{}", help="Input JSON")
@click.option("--user-dsid", type=str, default="dsid-u-0000000000000000-0000")
@click.option("--trust-tier", type=int, default=1)
def execute(manifest_hash: str, input_json: str, user_dsid: str, trust_tier: int):
    """Execute an agent by manifest hash."""
    import json
    
    from resonant_node.runtime.executor import AgentRuntime, ExecutionContext
    
    console.print(f"[bold]Executing agent: {manifest_hash}[/bold]")
    
    input_data = json.loads(input_json)
    
    context = ExecutionContext(
        session_id="cli-session",
        user_dsid=user_dsid,
        trust_tier=trust_tier,
        manifest_hash=manifest_hash,
    )
    
    async def run():
        # This is simplified - real impl would connect to running node
        console.print("[yellow]Note: Direct execution requires running node[/yellow]")
        console.print(f"Input: {input_data}")
        console.print(f"Context: {context}")
    
    asyncio.run(run())


@cli.group()
def key():
    """Key management commands."""
    pass


@key.command("generate")
@click.option(
    "--type",
    "id_type",
    type=click.Choice(["user", "org", "agent", "node"]),
    default="user",
)
@click.option("--output", "-o", type=click.Path(), default=None)
def key_generate(id_type: str, output: str):
    """Generate a new keypair and DSID."""
    from resonant_node.core.crypto import generate_keypair, derive_dsid
    
    public_key, private_key = generate_keypair()
    dsid = derive_dsid(public_key, id_type)
    
    console.print(f"[bold green]Generated {id_type} identity[/bold green]")
    console.print(f"DSID: {dsid}")
    console.print(f"Public Key: {public_key.hex()}")
    console.print(f"Private Key: {private_key.hex()}")
    console.print("\n[yellow]⚠️  Save your private key securely![/yellow]")
    
    if output:
        import json
        data = {
            "dsid": dsid,
            "type": id_type,
            "public_key": public_key.hex(),
            "private_key": private_key.hex(),
        }
        with open(output, "w") as f:
            json.dump(data, f, indent=2)
        console.print(f"Saved to: {output}")


@key.command("verify")
@click.argument("dsid")
def key_verify(dsid: str):
    """Verify DSID format and checksum."""
    from resonant_node.core.crypto import validate_dsid
    
    if validate_dsid(dsid):
        console.print(f"[green]✓ Valid DSID: {dsid}[/green]")
    else:
        console.print(f"[red]✗ Invalid DSID: {dsid}[/red]")


if __name__ == "__main__":
    cli()
