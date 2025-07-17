# Bandwidth Limiting Script for Windows
# Run this script as Administrator to enable bandwidth limiting

param(
    [string]$Action = "help",
    [int]$LimitMbps = 1
)

function Show-Help {
    Write-Host "Video Streaming Bandwidth Limiter" -ForegroundColor Green
    Write-Host "=================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Usage:" -ForegroundColor Yellow
    Write-Host "  .\bandwidth_limiter.ps1 -Action limit -LimitMbps 1    # Limit to 1 Mbps"
    Write-Host "  .\bandwidth_limiter.ps1 -Action remove                # Remove limits"
    Write-Host "  .\bandwidth_limiter.ps1 -Action status                # Show current limits"
    Write-Host ""
    Write-Host "Actions:" -ForegroundColor Yellow
    Write-Host "  limit   - Apply bandwidth limitation"
    Write-Host "  remove  - Remove bandwidth limitation"
    Write-Host "  status  - Show current QoS policies"
    Write-Host "  help    - Show this help message"
    Write-Host ""
    Write-Host "Examples:" -ForegroundColor Cyan
    Write-Host "  # Limit Python applications to 500 Kbps"
    Write-Host "  .\bandwidth_limiter.ps1 -Action limit -LimitMbps 0.5"
    Write-Host ""
    Write-Host "  # Limit to 2 Mbps"
    Write-Host "  .\bandwidth_limiter.ps1 -Action limit -LimitMbps 2"
    Write-Host ""
    Write-Host "Note: This script requires Administrator privileges" -ForegroundColor Red
}

function Test-AdminRights {
    $currentUser = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($currentUser)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Set-BandwidthLimit {
    param([int]$LimitMbps)
    
    if (-not (Test-AdminRights)) {
        Write-Error "This action requires Administrator privileges. Please run PowerShell as Administrator."
        return
    }
    
    $limitBps = $LimitMbps * 1MB
    
    try {
        # Remove existing policy if it exists
        Remove-NetQosPolicy -Name "VideoStreamLimit" -Confirm:$false -ErrorAction SilentlyContinue
        
        # Create new QoS policy
        Write-Host "Setting bandwidth limit to $LimitMbps Mbps for Python applications..." -ForegroundColor Yellow
        
        New-NetQosPolicy -Name "VideoStreamLimit" `
                        -AppPathNameMatchCondition "python.exe" `
                        -ThrottleRateActionBitsPerSecond $limitBps `
                        -Confirm:$false | Out-Null
        
        Write-Host "Bandwidth limit applied successfully!" -ForegroundColor Green
        Write-Host "Policy: VideoStreamLimit" -ForegroundColor Cyan
        Write-Host "Target: python.exe" -ForegroundColor Cyan
        Write-Host "Limit: $LimitMbps Mbps ($limitBps bits/sec)" -ForegroundColor Cyan
        
    } catch {
        Write-Error "Failed to set bandwidth limit: $($_.Exception.Message)"
    }
}

function Remove-BandwidthLimit {
    if (-not (Test-AdminRights)) {
        Write-Error "This action requires Administrator privileges. Please run PowerShell as Administrator."
        return
    }
    
    try {
        Write-Host "Removing bandwidth limitations..." -ForegroundColor Yellow
        Remove-NetQosPolicy -Name "VideoStreamLimit" -Confirm:$false -ErrorAction SilentlyContinue
        Write-Host "Bandwidth limitations removed successfully!" -ForegroundColor Green
        
    } catch {
        Write-Error "Failed to remove bandwidth limit: $($_.Exception.Message)"
    }
}

function Show-Status {
    Write-Host "Current QoS Policies:" -ForegroundColor Yellow
    Write-Host "=====================" -ForegroundColor Yellow
    
    $policies = Get-NetQosPolicy -ErrorAction SilentlyContinue
    
    if ($policies) {
        foreach ($policy in $policies) {
            Write-Host ""
            Write-Host "Policy Name: $($policy.Name)" -ForegroundColor Cyan
            Write-Host "App Path: $($policy.AppPathNameMatchCondition)" -ForegroundColor White
            Write-Host "Throttle Rate: $($policy.ThrottleRateActionBitsPerSecond) bits/sec" -ForegroundColor White
            
            if ($policy.ThrottleRateActionBitsPerSecond) {
                $mbps = [math]::Round($policy.ThrottleRateActionBitsPerSecond / 1MB, 2)
                Write-Host "Throttle Rate: $mbps Mbps" -ForegroundColor White
            }
        }
    } else {
        Write-Host "No QoS policies found." -ForegroundColor Green
    }
    
    Write-Host ""
    Write-Host "To test the video streaming application:" -ForegroundColor Yellow
    Write-Host "1. Apply bandwidth limit: .\bandwidth_limiter.ps1 -Action limit -LimitMbps 1"
    Write-Host "2. Run server: python server.py"
    Write-Host "3. Run client: python client.py"
    Write-Host "4. Observe resolution adaptation in the client"
    Write-Host "5. Remove limit: .\bandwidth_limiter.ps1 -Action remove"
}

# Main script execution
switch ($Action.ToLower()) {
    "limit" {
        Set-BandwidthLimit -LimitMbps $LimitMbps
    }
    "remove" {
        Remove-BandwidthLimit
    }
    "status" {
        Show-Status
    }
    "help" {
        Show-Help
    }
    default {
        Write-Host "Invalid action: $Action" -ForegroundColor Red
        Write-Host ""
        Show-Help
    }
}

Write-Host ""
Write-Host "Alternative bandwidth limiting methods:" -ForegroundColor Magenta
Write-Host "1. Clumsy (GUI tool): http://jagt.github.io/clumsy/"
Write-Host "2. NetLimiter (Commercial): https://www.netlimiter.com/"
Write-Host "3. Windows built-in QoS: Group Policy Editor"
