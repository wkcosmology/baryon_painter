import numpy as np

import matplotlib.pyplot as plt

import cosmotools.power_spectrum_tools
import cosmotools.plotting

pi = np.pi

def plot_samples(output_true, output_pred, input, output_pred_var=None,
                 n_sample=4, 
                 input_label="", 
                 output_labels=[],
                 plot_var=False,
                 n_feature_per_field=1,
                 tile_size=1):
    
    rows_per_sample = 2 if output_pred_var is None else 3
    n_row = rows_per_sample*min(output_true.shape[0], n_sample)
    n_col = (output_true.shape[1]+n_feature_per_field)
    
    fig, ax = plt.subplots(n_row, n_col, sharex=True, sharey=True, figsize=(n_col*tile_size, n_row*tile_size))
    fig.subplots_adjust(hspace=0.02, wspace=0.02*n_col/n_row)
    
    # Different colormaps for different tracers
    imshow_kwargs = [{"cmap" : "viridis", "vmin" : -1, "vmax" : 1},
                     {"cmap" : "magma", "vmin" : -1, "vmax" : 1},
                     {"cmap" : "plasma", "vmin" : -1, "vmax" : 1},
                     {"cmap" : "inferno", "vmin" : -1, "vmax" : 1}]
    # Plot input
    for i in range(min(input.shape[0], n_sample)):
        s = input[i].squeeze()
            
        if n_feature_per_field == 1:
            ax[2*i,0].imshow(s, **imshow_kwargs[0])
            ax[2*i+1,0].axis("off")
        else:
            for j in range(n_feature_per_field):
                ax[2*i,j].imshow(s[j], **imshow_kwargs[0])
                ax[2*i+1,j].axis("off")
        
        
    # Plot output
    for i in range(min(output_true.shape[0], n_sample)):
        for j in range(output_true.shape[1]):
            output_true_plot = output_true[i,j].squeeze()
            output_pred_plot = output_pred[i,j].squeeze()

            if n_feature_per_field == 1:
                ax[2*i,j+1].imshow(output_true_plot, **imshow_kwargs[j+1])
                ax[2*i+1,j+1].imshow(output_pred_plot, **imshow_kwargs[j+1])
                if output_pred_var is not None:
                    output_pred_var_plot = np.log(output_pred_var[i,j].squeeze())
                    kwargs = {k : v for k, v in imshow_kwargs[j+1].items() if k != "vmin" and k != "vmax"}
                    ax[2*i+2,j+1].imshow(output_pred_var_plot, **kwargs)
            else:
                ax[2*i,j+n_feature_per_field].imshow(output_true_plot, **imshow_kwargs[j//n_feature_per_field+1])
                ax[2*i+1,j+n_feature_per_field].imshow(output_pred_plot, **imshow_kwargs[j//n_feature_per_field+1])
                if output_pred_var is not None:
                    output_pred_var_plot = np.log(output_pred_var[i,j].squeeze())
                    kwargs = {k : v for k, v in imshow_kwargs[j//n_feature_per_field+1].items() if k != "vmin" and k != "vmax"}
                    ax[2*i+2,j+n_feature_per_field].imshow(output_pred_var_plot, **kwargs)
    
    for p in ax.flat:
        p.grid(False)
        p.set_axis_off()

    ax[0,0].set_title(input_label) 
    if output_labels != []:
        for i in range(len(output_labels)):
            ax[0,n_feature_per_field*(i+1)].set_title(output_labels[i])
        
    return fig, ax


def plot_power_spectra(output_true, output_pred, input, L,
                       mode="auto", 
                       output_labels=[], plot_size=(4,2), 
                       input_transform=None,
                       output_transforms=None,
                       n_k_bin=20, logspaced_k_bins=True,
                       plot_mean_deviation=True,
                       n_feature_per_field=1):
    n_row = 2
    n_col = output_true.shape[1]//n_feature_per_field
        
    fig, ax = plt.subplots(n_row, n_col, sharex=True, figsize=(plot_size[0]*n_col, plot_size[1]*n_row))
    if n_col == 1:
        ax = np.atleast_2d(ax).T
        
    fig.subplots_adjust(left=0.2, bottom=0.15, hspace=0, wspace=0.3)
    
    k_min = 2*pi/L
    k_max = 2*pi/L*output_true.shape[-1]/2
    
    Pk_deviation = np.zeros((output_true.shape[0], n_col, n_k_bin))
        
    for i in range(n_col):
        for j in range(output_true.shape[0]):
            if output_transforms is None:
                out_transform = lambda x: x
            else:
                out_transform = output_transforms[j][i]
            if input_transform is None:
                in_transform = lambda x: x
            else:
                in_transform = input_transform[j]

            A_true = out_transform(output_true[j,i*n_feature_per_field:(i+1)*n_feature_per_field]).squeeze()
            A_pred = out_transform(output_pred[j,i*n_feature_per_field:(i+1)*n_feature_per_field]).squeeze()
            if mode.lower() == "auto":
                B_true = A_true
                B_pred = A_pred
            elif mode.lower() == "cross":
                B_true = in_transform(input[j,:n_feature_per_field]).squeeze()
                B_pred = in_transform(input[j,:n_feature_per_field]).squeeze()
            else:
                raise ValueError("Invalid mode: {}.".format(mode))
                
            Pk_true, k, Pk_var_true, n_mode = cosmotools.power_spectrum_tools.pseudo_Pofk(A_true, B_true, L, k_min=k_min, k_max=k_max, n_k_bin=n_k_bin, logspaced_k_bins=logspaced_k_bins)
            Pk_pred, k, Pk_var_pred, n_mode = cosmotools.power_spectrum_tools.pseudo_Pofk(A_pred, B_pred, L, k_min=k_min, k_max=k_max, n_k_bin=n_k_bin, logspaced_k_bins=logspaced_k_bins)
            
            Pk_deviation[j,i] = Pk_pred/Pk_true-1
            
            ax[0,i].loglog(k, k**2 * Pk_true, alpha=0.2, c="C0", label="")
            ax[0,i].loglog(k, k**2 * Pk_pred, alpha=0.2, c="C1", label="")
            
            ax[1,i].semilogx(k, Pk_pred/Pk_true-1, alpha=0.2, c="C0", label="")
            
        if plot_mean_deviation:
            ax[1,i].semilogx(k, Pk_deviation.mean(axis=0)[i], alpha=1.0, linewidth=2, c="C0", label="")
            
    for p in ax.flat:
        p.grid(False)
        
    
    if len(output_labels) >= n_col:
        for i in range(n_col):
            ax[0,i].set_title(output_labels[i])
    
    for p in ax[0]:
        p.set_ylabel(r"$k^2 P(k)$")
        p.plot([], [], alpha=0.5, c="C0", label="Truth")
        p.plot([], [], alpha=0.5, c="C1", label="Predicted")
        p.legend(frameon=False)
        
    for p in ax[1]:
        p.set_ylim(-0.5, 0.5)
        p.axhline(0)
        p.set_ylabel("Fractional\ndifference")
        p.set_xlabel(r"$k$ [Mpc$^{-1}$ h]")
        
    if mode.lower() == "auto":
        fig.suptitle("Auto power spectrum")
    else:
        fig.suptitle("Cross power spectrum")
        
    return fig, ax

def plot_histogram(output_true, output_pred, n_sample=1, labels=[], plot_size=(4,2), n_bin=100, x_logscale=False, y_logscale=False, **plot_kwargs):
    n_col = output_true.shape[1]
    
    fig, ax = plt.subplots(1, n_col, sharex=True, figsize=(plot_size[0]*n_col, plot_size[1]))
    if n_col == 1:
        ax = np.atleast_1d(ax)
        
    for i in range(n_col):
        d_true = output_true[:n_sample,i].flatten()
        d_pred = output_pred[:n_sample,i].flatten()

        plot_min = min(d_true.min(), d_pred.min())
        plot_max = max(d_true.max(), d_pred.max())
        if x_logscale:
            bins = np.logspace(np.log10(plot_min), np.log10(plot_max), n_bin, endpoint=True)
        else:
            bins = np.linspace(plot_min, plot_max, n_bin, endpoint=True)

        ax[i].hist(d_true, bins=bins, density=True, alpha=0.5, facecolor="C0", label="Truth", **plot_kwargs)
        ax[i].hist(d_pred, bins=bins, density=True, alpha=0.5, facecolor="C1", label="Predicted", **plot_kwargs)
    
    for p in ax:
        p.grid(False)
        p.legend()
        if x_logscale:
            p.set_xscale("log")
        if y_logscale:
            p.set_yscale("log")
        
    if len(labels) >= n_col:
        for i in range(n_col):
            ax[i].set_xlabel(labels[i])
            
    return fig, ax